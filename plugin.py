"""Ignore selected QQ users before MaiBot processes their messages."""
from __future__ import annotations

from typing import Any, Optional

from maibot_sdk import Field, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder

CONFIG_SCHEMA_VERSION = "0.1.0"


class PluginSection(PluginConfigBase):
    """Basic plugin switches."""

    __ui_label__ = "插件设置"

    name: str = Field(
        default="qq_ignore_filter",
        description="插件名称",
        json_schema_extra={"disabled": True},
    )
    config_version: str = Field(
        default=CONFIG_SCHEMA_VERSION,
        description="配置文件版本",
        json_schema_extra={"disabled": True},
    )
    enabled: bool = Field(
        default=True,
        description="是否启用插件",
        json_schema_extra={"label": "启用插件"},
    )


class IgnoreSection(PluginConfigBase):
    """Users whose messages should be consumed before the main chat pipeline."""

    __ui_label__ = "忽略名单"

    blocked_user_ids: list[str] = Field(
        default=[],
        description="要忽略的 QQ 号列表，推荐使用这个精确匹配。",
        json_schema_extra={"label": "屏蔽 QQ 号", "hint": "例如 [\"123456\"]"},
    )
    blocked_display_names: list[str] = Field(
        default_factory=list,
        description="显示名/群名片兜底匹配列表。QQ 号未知时临时使用，名称改变会失效。",
        json_schema_extra={"label": "屏蔽显示名兜底"},
    )
    apply_to_group: bool = Field(
        default=True,
        description="是否拦截群聊消息。",
        json_schema_extra={"label": "拦截群聊"},
    )
    apply_to_private: bool = Field(
        default=True,
        description="是否拦截私聊消息。",
        json_schema_extra={"label": "拦截私聊"},
    )
    log_ignored: bool = Field(
        default=True,
        description="命中忽略名单时写入日志。",
        json_schema_extra={"label": "记录拦截日志"},
    )


class QQIgnoreFilterConfig(PluginConfigBase):
    """Complete config."""

    plugin: PluginSection = Field(default_factory=PluginSection)
    ignore: IgnoreSection = Field(default_factory=IgnoreSection)


class QQIgnoreFilterPlugin(MaiBotPlugin):
    """Abort inbound messages from configured QQ users."""

    config_model = QQIgnoreFilterConfig

    async def on_load(self) -> None:
        self.ctx.logger.info(
            "[qq-ignore-filter] loaded: ids=%s names=%s",
            self.config.ignore.blocked_user_ids,
            self.config.ignore.blocked_display_names,
        )

    async def on_unload(self) -> None:
        self.ctx.logger.info("[qq-ignore-filter] unloaded")

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        self.set_plugin_config(config_data)
        self.ctx.logger.info("[qq-ignore-filter] config updated: scope=%s version=%s", scope, version)

    @HookHandler(
        "chat.receive.after_process",
        name="qq_ignore_guard",
        description="按 QQ 号/显示名忽略指定用户的入站消息",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
        timeout_ms=1000,
        error_policy=ErrorPolicy.SKIP,
    )
    async def handle_receive(self, message: Optional[dict] = None, **kwargs: Any):
        if not self.config.plugin.enabled:
            return None
        if not isinstance(message, dict):
            return None

        ctx = self._extract_context(message)
        if ctx["is_group"] and not self.config.ignore.apply_to_group:
            return None
        if not ctx["is_group"] and not self.config.ignore.apply_to_private:
            return None

        blocked_ids = {str(item).strip() for item in self.config.ignore.blocked_user_ids if str(item).strip()}
        blocked_names = {str(item).strip().lower() for item in self.config.ignore.blocked_display_names if str(item).strip()}

        user_id = ctx["user_id"]
        names = {name.lower() for name in ctx["names"] if name}
        matched_by_id = bool(user_id and user_id in blocked_ids)
        matched_by_name = bool(names & blocked_names)
        if not matched_by_id and not matched_by_name:
            return None

        if self.config.ignore.log_ignored:
            self.ctx.logger.info(
                "[qq-ignore-filter] ignored message from user_id=%s names=%s group_id=%s reason=%s",
                user_id or "<unknown>",
                sorted(names),
                ctx["group_id"] or "<private>",
                "id" if matched_by_id else "display_name",
            )
        return {"action": "abort"}

    @staticmethod
    def _extract_context(message: dict) -> dict[str, Any]:
        msg_info = message.get("message_info") or {}
        if not isinstance(msg_info, dict):
            msg_info = {}
        user_info = msg_info.get("user_info") or {}
        if not isinstance(user_info, dict):
            user_info = {}
        group_info = msg_info.get("group_info") or {}
        if not isinstance(group_info, dict):
            group_info = {}
        additional_config = msg_info.get("additional_config") or {}
        if not isinstance(additional_config, dict):
            additional_config = {}

        user_id = str(
            user_info.get("user_id")
            or message.get("user_id")
            or additional_config.get("platform_io_target_user_id")
            or ""
        ).strip()
        group_id = str(
            group_info.get("group_id")
            or additional_config.get("platform_io_target_group_id")
            or ""
        ).strip()
        names = [
            str(user_info.get("user_nickname") or "").strip(),
            str(user_info.get("user_cardname") or "").strip(),
            str(user_info.get("nickname") or "").strip(),
            str(user_info.get("card") or "").strip(),
            str(message.get("user_nickname") or "").strip(),
            str(message.get("user_cardname") or "").strip(),
        ]
        return {"user_id": user_id, "group_id": group_id, "is_group": bool(group_id), "names": names}


def create_plugin() -> QQIgnoreFilterPlugin:
    """MaiBot plugin factory."""
    return QQIgnoreFilterPlugin()
