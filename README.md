# QQ 忽略过滤器（nxtsl.qq-ignore-filter）

在 MaiBot 主聊天链路处理消息前，按 QQ 号或显示名拦截指定用户消息。

## 配置

```toml
[ignore]
blocked_user_ids = ["123456"]
blocked_display_names = []
apply_to_group = true
apply_to_private = true
log_ignored = true
```

优先使用 `blocked_user_ids` 精确匹配。`blocked_display_names` 只适合作为临时兜底，因为群名片或昵称变更后会失效。

## 行为

- `apply_to_group = true` 时拦截群聊消息。
- `apply_to_private = true` 时拦截私聊消息。
- 命中后返回 `{"action": "abort"}`，阻止消息继续进入主链。
