"""插件配置常量与默认值。AstrBot 通过 _conf_schema.json 构建实际配置。"""

DEFAULT_DATA_DIR = "data/dyf"

DEFAULT_SOURCES = {
    "douyin": {
        "enabled": True,
        "types": {
            "text": True,
            "image": True,
            "video_card": True,
            "emoji": False,
            "voice": False,
            "other": True,
        },
    }
}
