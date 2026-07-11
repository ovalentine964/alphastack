# Agent Configuration Guide

## Current Configuration Summary

**Agent:** Main Agent  
**Model:** xiaomi/mimo-v2.5-pro (MiMo V2.5 Pro)  
**Workspace:** /home/work/.openclaw/workspace  
**Session Count:** 232 sessions  
**Last Updated:** 2026-07-11

## Model Configuration

### Current Model
- **Provider:** xiaomi
- **Model ID:** mimo-v2.5-pro
- **Display Name:** MiMo V2.5 Pro
- **Reasoning:** Enabled
- **Context Window:** 1,048,576 tokens
- **Max Output Tokens:** 65,536
- **Input Types:** Text only
- **Cost:** Free (0 input/output)

### Model Capabilities
- **Reasoning:** Yes (can toggle with /reasoning command)
- **Thinking Mode:** Medium (hidden by default)
- **Context Window:** 1M tokens (very large)
- **Max Output:** 65K tokens

## Agent Behavior Configuration

### Workspace Settings
- **Workspace Root:** /home/work/.openclaw/workspace
- **File Operations:** Restricted to workspace only (tools.fs.workspaceOnly = true)
- **Compaction Mode:** Safeguard (preserves context during long conversations)

### Tool Configuration
- **Tool Profile:** Full access
- **Disabled Tools:** TTS (text-to-speech)
- **Web Search:** Disabled (using mimo-search plugin instead)
- **Exec Security:** Full (no restrictions on shell commands)
- **Exec Ask Mode:** Off (no confirmation prompts)

### Session Management
- **DM Scope:** Per-channel-peer (separate sessions per channel/user)
- **Reset Mode:** Idle (sessions reset after inactivity)

## Channel Configuration

### Enabled Channels
1. **Telegram** - Enabled
   - Bot Token: Configured
   - DM Policy: Pairing (requires pairing for DMs)
   - Group Policy: Open (responds in groups)

2. **Feishu** - Enabled
3. **WeChat** - Enabled (openclaw-weixin)
4. **DingTalk** - Enabled (dingtalk-connector)
5. **WhatsApp** - Enabled

### Disabled Channels
- **QQ Bot** - Disabled

## Plugin Configuration

### Enabled Plugins
1. **mimo-search** - Web search functionality
2. **feishu** - Feishu integration
3. **qqbot** - QQ Bot integration (disabled)
4. **openclaw-weixin** - WeChat integration
5. **dingtalk-connector** - DingTalk integration
6. **whatsapp** - WhatsApp integration

### Plugin Loading Paths
- /opt/mimo-claw-seed/channel-extensions/feishu
- /opt/mimo-claw-seed/channel-extensions/qqbot
- /opt/mimo-claw-seed/channel-extensions/openclaw-weixin
- /opt/mimo-claw-seed/channel-extensions/dingtalk-connector
- /opt/mimo-claw-seed/channel-extensions/whatsapp
- /opt/mimo-claw-seed/extensions/mimo-search

## Gateway Configuration

### Network Settings
- **Port:** 18789
- **Mode:** Local
- **Bind:** LAN (accessible on local network)
- **Control UI:** Enabled (dangerouslyDisableDeviceAuth = true)

### Authentication
- **Auth Mode:** Token-based
- **Token:** Configured via environment variable

### Tailscale
- **Mode:** Off
- **Reset on Exit:** False

### Node Restrictions
- **Denied Commands:** camera.snap, camera.clip, screen.record, contacts.add, calendar.add, reminders.add, sms.send

## Security Configuration

### Command Restrictions
- **Native Commands:** Auto
- **Native Skills:** Auto
- **Restart:** Enabled
- **Owner Display:** Raw
- **Owner Allow From:** telegram:8496983249

### Diagnostics
- **Enabled:** Yes
- **Flags:** All (*)

## Usage Patterns

### Current Usage
- **Total Sessions:** 232
- **Active Sessions:** Multiple concurrent sessions
- **Session Types:** Direct messages, group chats, subagents

### Session Lifecycle
- Sessions are created per channel/user combination
- Sessions reset after idle period
- Each session maintains its own context and memory

## Customization Options

### Adding New Models
To add a new model provider, edit ~/.openclaw/openclaw.json:

```json
{
  "models": {
    "providers": {
      "new-provider": {
        "baseUrl": "https://api.example.com",
        "apiKey": "your-api-key",
        "api": "openai-completions",
        "models": [
          {
            "id": "model-id",
            "name": "Model Name",
            "reasoning": true,
            "input": ["text"],
            "cost": {
              "input": 0.01,
              "output": 0.02
            },
            "contextWindow": 128000,
            "maxTokens": 4096
          }
        ]
      }
    }
  }
}
```

### Changing Default Model
Update the agents.defaults.model.primary field:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "provider/model-id"
      }
    }
  }
}
```

### Enabling/Disabling Channels
Toggle channel.enabled field:

```json
{
  "channels": {
    "channel-name": {
      "enabled": true
    }
  }
}
```

## Environment Variables

The following environment variables are used:
- **MIMO_API_BASE_URL** - Base URL for MiMo API
- **MIMO_API_KEY** - API key for MiMo API
- **MIMO_SEARCH_TOKEN** - Token for mimo-search plugin
- **OPENCLAW_GATEWAY_TOKEN** - Gateway authentication token

## File Locations

### Configuration
- **Main Config:** ~/.openclaw/openclaw.json
- **Agent Directory:** ~/.openclaw/agents/main/
- **Session Files:** ~/.openclaw/agents/main/sessions/

### Workspace
- **Root:** /home/work/.openclaw/workspace
- **Skills:** ~/.openclaw/skills/
- **Plugins:** ~/.openclaw/plugin-skills/

### Logs
- **Session Logs:** ~/.openclaw/agents/main/sessions/*.jsonl
- **Trajectory Logs:** ~/.openclaw/agents/main/sessions/*.trajectory.jsonl

## Troubleshooting

### Common Issues

1. **Model Not Found**
   - Verify model ID in providers section
   - Check provider configuration
   - Ensure API key is valid

2. **Channel Not Responding**
   - Check channel.enabled status
   - Verify channel-specific configuration
   - Check plugin loading paths

3. **Tool Errors**
   - Verify tool is not in deny list
   - Check exec security settings
   - Ensure workspace permissions

4. **Session Issues**
   - Check session.reset.mode
   - Verify dmScope settings
   - Check for session file corruption

### Debug Commands

```bash
# Check gateway status
openclaw gateway status

# View recent sessions
ls -la ~/.openclaw/agents/main/sessions/*.jsonl | tail -10

# Check configuration
cat ~/.openclaw/openclaw.json | jq .

# View logs
tail -f ~/.openclaw/logs/*.log
```

## Performance Optimization

### Model Settings
- **Context Window:** 1M tokens (large context for complex tasks)
- **Max Output:** 65K tokens (generous output limit)
- **Reasoning:** Enabled for complex analysis

### Session Management
- **Compaction:** Safeguard mode preserves important context
- **Reset:** Idle mode prevents stale sessions
- **Scope:** Per-channel-peer for organized sessions

### Tool Usage
- **Full Profile:** All tools available
- **Workspace Only:** Prevents file system escape
- **Exec Security:** Full access for development tasks

## Future Enhancements

### Potential Improvements
1. **Multi-Model Support** - Add additional model providers
2. **Advanced Reasoning** - Configure reasoning depth and style
3. **Memory Management** - Implement memory consolidation
4. **Plugin Extensions** - Add custom plugins for specific tasks
5. **Channel Optimization** - Fine-tune channel-specific behavior

### Scaling Considerations
- **Session Limits:** Monitor session count and cleanup old sessions
- **Memory Usage:** Track workspace size and archive old files
- **API Costs:** Monitor model usage if using paid providers
- **Network Traffic:** Optimize channel communication patterns

---

*Last Updated: 2026-07-11*
