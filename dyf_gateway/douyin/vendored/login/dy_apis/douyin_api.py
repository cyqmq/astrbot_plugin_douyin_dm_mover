"""dy_apis.douyin_api 最小 shim。

DouYin_Spider 的 ``builder/auth.py`` 顶部 ``from dy_apis import douyin_api``，
但登录链路（login_api.py）只依赖 ``auth.request`` / cookie 处理，并不引用本模块的
IM/HTTP 全量实现。这里仅提供 ``auth.py`` 实际用到的两个静态方法，避免整包引入
google-protobuf / lxml / builder.proto。

- ``get_device_id(auth)``：auth.get_webid() 的兜底来源；返回空则回落 generate_webid。
- ``get_my_uid(auth)``：auth.get_uid() 的懒解析来源；返回 auth.uid（登录后由服务端写入）。
"""


class DouyinAPI:
    @staticmethod
    def get_device_id(auth) -> str:
        return str(getattr(auth, "device_id", None) or "") or ""

    @staticmethod
    def get_my_uid(auth):
        return getattr(auth, "uid", None)
