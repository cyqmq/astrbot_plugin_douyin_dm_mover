// Node 桥接：用 @alemonjs/douyin 的底层登录接口完成 扫码 → 2046 短信 MFA → 会话。
// 协议为 NDJSON 行：
//   插件 → bridge: {"cmd":"start","timeout":300} | {"cmd":"mfa_code","code":"..."} | {"cmd":"stop"}
//   bridge → 插件: {"event":"ready"} | {"event":"qrcode","token","qrcodeBase64"}
//                  | {"event":"mfa_required","kind","maskedMobile"}
//                  | {"event":"status","text"} | {"event":"login_ok","platformUid","cookies","userData"}
//                  | {"event":"login_expired","detail"} | {"event":"login_failed","error"}
//                  | {"event":"fatal","error"}
import { DouyinHttp, getQrcode, checkQrconnect, sendQrMfaCode, validateQrMfaCode, QR_POLL_INTERVAL_MS } from "@alemonjs/douyin/sdk";
import readline from "node:readline";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function emit(obj) {
	process.stdout.write(JSON.stringify(obj) + "\n");
}

const VERIFY_WAY_PRIORITY = [
	"assist_mobile_sms_verify",
	"mobile_sms_verify",
	"assist_mobile_up_sms_verify",
	"pwd_verify"
];
const QR_BIZ_PARAM_KEYS = [
	"passport_mfa_retry_tag",
	"std_verify_flow_id",
	"std_verify_scene",
	"std_verify_template",
	"std_verify_token",
	"std_verify_type",
	"std_verify_way"
];

function pickWay(ways) {
	const list = ways || [];
	for (const name of VERIFY_WAY_PRIORITY) {
		const w = list.find((x) => x && x.verify_way === name);
		if (w) return w;
	}
	return null;
}

function pickBiz(params) {
	const result = {};
	if (!params) return result;
	for (const key of QR_BIZ_PARAM_KEYS) {
		const v = params[key];
		if (v !== null && v !== undefined) result[key] = String(v);
	}
	return result;
}

function sessionFromConfirmed(http, qrToken, userData) {
	const u = userData || {};
	const uid =
		u.user_id_str ??
		(u.user_id !== null && u.user_id !== undefined ? String(u.user_id) : undefined) ??
		http.jar.get("uid_tt");
	if (!uid) throw new Error("扫码确认成功但无法确定平台 uid（uid_tt cookie / user_data 缺失）");
	const session = { platformUid: uid, cookies: http.getCookies(), qrToken };
	if (userData) session.userData = userData;
	return session;
}

let http;
try {
	http = new DouyinHttp({});
} catch (e) {
	emit({ event: "fatal", error: `初始化 DouyinHttp 失败: ${e?.message ?? e}` });
	process.exit(1);
}

let running = false;
let token = null;
let extraBody = {};
let mfaDone = false;
let codeQueue = [];

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on("line", (line) => {
	let m;
	try {
		m = JSON.parse(line);
	} catch {
		return;
	}
	if (m.cmd === "start") {
		start(m).catch((e) => {
			emit({ event: "login_failed", error: String(e?.message ?? e) });
			running = false;
		});
	} else if (m.cmd === "mfa_code") {
		codeQueue.push(String(m.code ?? "").trim());
	} else if (m.cmd === "stop") {
		running = false;
		process.exit(0);
	}
});

async function waitCode() {
	while (running) {
		if (codeQueue.length) return codeQueue.shift();
		await sleep(200);
	}
	return "";
}

async function pollUpSms(challenge, way) {
	const content = way.sms_content || "YZ";
	emit({ event: "status", text: `请用安全手机（${way.mobile ?? ""}）编辑短信"${content}"发送到 ${way.channel_mobile ?? ""}` });
	const deadline = Date.now() + 180000;
	let last;
	while (Date.now() < deadline) {
		await sleep(3000);
		try {
			last = await validateQrMfaCode(http, challenge, way.verify_way || "assist_mobile_up_sms_verify");
		} catch {
			continue;
		}
		if (last && last.data && last.data.ticket) {
			emit({ event: "status", text: "短信验证通过" });
			return true;
		}
	}
	emit({ event: "status", text: `上行短信验证超时: ${last?.data?.error_code ?? "-"} ${last?.data?.description ?? ""}` });
	return false;
}

async function handleMfa(d) {
	const challenge = {
		encrypt_uid: d.encrypt_uid,
		biz_params: d.biz_params,
		common_params: d.common_params
	};
	const way = pickWay(d.verify_ways);
	if (!way || !way.verify_way) {
		emit({ event: "status", text: "无可支持的验证方式，请在抖音 App 完成该次身份验证" });
		return;
	}
	if (way.verify_way === "assist_mobile_up_sms_verify") {
		const ok = await pollUpSms(challenge, way);
		if (ok) {
			mfaDone = true;
			extraBody = pickBiz(d.biz_params);
		}
		return;
	}
	if (way.verify_way === "pwd_verify") {
		emit({ event: "status", text: "扫码触发密码二次验证，但本插件仅支持短信验证，请在抖音 App 完成" });
		return;
	}
	const tryWays =
		way.verify_way === "mobile_sms_verify"
			? [way.verify_way, "assist_mobile_sms_verify"]
			: [way.verify_way];
	let sent = null;
	let usedWay = null;
	for (const candidate of tryWays) {
		const r = await sendQrMfaCode(http, challenge, candidate);
		if (r && r.message === "success") {
			sent = r;
			usedWay = candidate;
			break;
		}
		sent = r;
	}
	if (!usedWay) {
		const up = (d.verify_ways || []).find((w) => w && w.verify_way === "assist_mobile_up_sms_verify");
		if (up && up.verify_way) {
			const ok = await pollUpSms(challenge, up);
			if (ok) {
				mfaDone = true;
				extraBody = pickBiz(d.biz_params);
			}
		} else {
			emit({ event: "login_failed", error: `发送验证码失败: ${sent?.message ?? "unknown"}${sent?.data?.description ? ` - ${sent.data.description}` : ""}` });
			running = false;
		}
		return;
	}
	const maskedMobile = sent?.data?.mobile ?? way.mobile;
	emit({ event: "mfa_required", kind: "sms", maskedMobile: maskedMobile !== null && maskedMobile !== undefined ? String(maskedMobile) : null });
	const code = await waitCode();
	if (!code) {
		emit({ event: "status", text: "未收到验证码，继续等待（可在抖音 App 完成验证）" });
		return;
	}
	const val = await validateQrMfaCode(http, challenge, usedWay, code);
	if (val && val.data && val.data.ticket) {
		emit({ event: "status", text: "验证码校验通过，等待扫码确认" });
	} else {
		emit({ event: "status", text: `验证码校验未通过: ${val?.data?.error_code ?? "-"} ${val?.data?.description ?? ""}` });
	}
	mfaDone = true;
	extraBody = pickBiz(d.biz_params);
}

async function start(m) {
	if (running) return;
	running = true;
	const timeoutMs = (m.timeout || 300) * 1000;
	const deadline = Date.now() + timeoutMs;
	try {
		const info = await getQrcode(http);
		token = info.token;
		emit({ event: "qrcode", token, qrcodeBase64: info.qrcodeBase64 });
		let notifiedVerifyCenter = false;
		while (running && Date.now() < deadline) {
			let d;
			try {
				d = await checkQrconnect(http, token, extraBody);
			} catch {
				await sleep(QR_POLL_INTERVAL_MS);
				continue;
			}
			if ((d.verify_center_decision_conf || d.verify_center_secondary_decision_conf) && !notifiedVerifyCenter) {
				notifiedVerifyCenter = true;
				emit({ event: "status", text: "扫码触发安全验证，请在浏览器完成验证后返回本页" });
			}
			if (!mfaDone && (d.account_flow === "verify" || (d.biz_params !== null && d.biz_params !== undefined))) {
				await handleMfa(d);
				continue;
			}
			const st = d.status;
			if (st === "confirmed") {
				const session = sessionFromConfirmed(http, token, d.user_data);
				emit({ event: "login_ok", platformUid: session.platformUid, cookies: session.cookies, userData: session.userData || null, deviceId: http.deviceId || null });
				running = false;
				return;
			}
			if (st === "expired") {
				emit({ event: "login_expired", detail: "二维码已过期，请刷新后重新扫码" });
				running = false;
				return;
			}
			await sleep(QR_POLL_INTERVAL_MS);
		}
		if (running) {
			emit({ event: "login_failed", error: "登录超时，请重新发起扫码登录" });
			running = false;
		}
	} catch (e) {
		emit({ event: "login_failed", error: String(e?.message ?? e) });
		running = false;
	}
}

emit({ event: "ready" });
