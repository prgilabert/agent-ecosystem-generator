[project]
name = "{{mcp_name}}"
version = "0.1.0"
description = "{{mcp_description}}"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.0",
]

[project.scripts]
{{mcp_name}} = "{{mcp_module}}.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
