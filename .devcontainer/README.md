# SimpleChores Development Container

This development container provides a complete Home Assistant development environment for the SimpleChores integration.

## Quick Start

1. **Prerequisites**:
   - Docker Desktop installed and running
   - VS Code with Dev Containers extension (`ms-vscode-remote.remote-containers`)

2. **Open in Container**:
   ```bash
   code /Users/mordar/Downloads/personal/SimpleChores
   # VS Code will detect the devcontainer.json and prompt to "Reopen in Container"
   # Or use Command Palette: "Dev Containers: Reopen in Container"
   ```

3. **After Container Starts**:
   - Full Home Assistant development environment will be ready
   - Claude Code CLI will be installed and available
   - Your integration will be linked into the HA components directory
   - Tests will be linked into the HA test structure

## Running Tests

```bash
# Test your integration specifically
python -m pytest tests/components/simplechores/ -v

# Test with coverage
python -m pytest tests/components/simplechores/ --cov=homeassistant.components.simplechores --cov-report=html

# Run all Home Assistant tests (takes a while)
python -m pytest tests/ -k simplechores
```

## Development Workflow

```bash
# Lint your code
ruff check homeassistant/components/simplechores/

# Format your code  
ruff format homeassistant/components/simplechores/

# Type checking
mypy homeassistant/components/simplechores/

# Run Home Assistant with your integration
hass -c config --debug
```

## Container Features

- **Base**: Home Assistant development container (`ghcr.io/home-assistant/devcontainer:dev`)
- **Python**: 3.13 with all HA dependencies
- **Tools**: pytest, ruff, mypy, Claude Code CLI
- **Ports**: 8123 (HA), 9123 (HA Debug)
- **Mounts**: 
  - Home directory mounted for persistent access
  - Project mounted to `/workspaces/SimpleChores`

## File Structure in Container

```
/workspaces/SimpleChores/           # Your project
├── custom_components/SimpleChores/ # Your integration code
├── tests/                          # Your tests
└── .devcontainer/                  # This config

/usr/src/homeassistant/             # HA core
├── homeassistant/components/simplechores/ → symlinked to your code
├── tests/components/simplechores/          → symlinked to your tests
└── script/setup                    # HA development setup
```

This setup allows you to:
- Edit files in your local project
- Run tests using the full HA test framework
- Debug with proper HA context and dependencies
- Use Claude Code for AI-assisted development