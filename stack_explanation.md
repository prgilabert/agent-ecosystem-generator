# Construye tu propio stack de IA con Claude Code

**Claude Code es hoy (abril 2026) el stack más extensible para desarrollo asistido por IA**, superando a Windsurf y Devin en control granular, observabilidad local y composabilidad — a costa de una curva más empinada y ausencia de IDE visual nativo. Las seis primitivas que importan — **agents, skills, MCP, hooks, slash commands y CLAUDE.md** — convergieron en los últimos 12 meses hacia un modelo coherente: metadata siempre cargada + cuerpo bajo demanda (*progressive disclosure*) + enforcement determinista fuera del LLM. Este informe cubre cada primitiva a nivel "cómo construirlo yo mismo", con código funcional TypeScript/Python, snippets de configuración copy-paste, una arquitectura end-to-end y comparativa cruda con los competidores. El mensaje de fondo: **no necesitas frameworks ni abstracciones — la API de Anthropic + convenciones de archivos markdown + JSON-RPC 2.0 es todo**.

---

## 1. Agentes — loop, subagentes, patrones multi-agente

### 1.1 El loop canónico de un agente

Un agente LLM es **un bucle de tres pasos** (think → act → observe) más guardrails. Con la Messages API de Anthropic, el patrón es explícito: `stop_reason == "tool_use"` → ejecuta tool → inyecta `tool_result` → repite hasta `end_turn`.

```
user query ──► LLM ──┬─► stop_reason "end_turn" ──► return text
                     │
                     └─► stop_reason "tool_use" ──► execute ──► append tool_result
                                                                     │
                     ◄────────────────────────────────────────────── ┘
guards: max_iterations · token_budget · HITL checkpoint · timeout
```

El paper de referencia obligatoria es **"Building effective agents"** (Schluntz & Zhang, Anthropic, diciembre 2024). Sus principios: empieza con direct API calls, **no frameworks**; invierte tanto en el *Agent-Computer Interface* (descripción de tools) como en el prompt; muestra planning steps; define siempre stopping conditions; distingue *workflow* (orquestado por código determinista) de *agente* (el LLM dirige dinámicamente).

### 1.2 Agente propio en Python — versión production-ready

Lo esencial cabe en ~80 líneas. **No uses LangChain ni crewAI a menos que justifiques la abstracción** — el código directo es más debuggeable y más barato:

```python
import json, time, subprocess, pathlib
from anthropic import Anthropic, APIStatusError, RateLimitError

client = Anthropic()
MODEL = "claude-sonnet-4-5-20250929"

TOOLS = [
    {"name": "read_file", "description": "Read UTF-8 text file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "run_shell", "description": "Execute shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
]

def tool_read_file(args):
    p = pathlib.Path(args["path"])
    if not p.is_absolute(): return {"error": "path must be absolute"}
    return {"content": p.read_text(errors="replace")[:200_000]}

def tool_run_shell(args):
    try:
        r = subprocess.run(args["command"], shell=True, capture_output=True, text=True, timeout=30)
        return {"stdout": r.stdout[-8000:], "stderr": r.stderr[-4000:], "exit_code": r.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}

TOOL_IMPLS = {"read_file": tool_read_file, "run_shell": tool_run_shell}

SYSTEM = [{"type": "text",
           "text": "You are a senior SWE agent. Plan before acting. Verify with ground truth.",
           "cache_control": {"type": "ephemeral"}}]  # prompt caching

def robust_create(**kwargs):
    delay = 1.0
    for attempt in range(6):
        try: return client.messages.create(**kwargs)
        except (RateLimitError, APIStatusError) as e:
            if attempt == 5: raise
            time.sleep(delay); delay *= 2

def run_agent(user_input, max_iter=25, token_budget=500_000):
    messages = [{"role": "user", "content": user_input}]
    total = 0
    for _ in range(max_iter):
        r = robust_create(model=MODEL, max_tokens=4096, system=SYSTEM, tools=TOOLS, messages=messages)
        total += r.usage.input_tokens + r.usage.output_tokens
        if total > token_budget: raise RuntimeError("budget exceeded")
        messages.append({"role": "assistant", "content": r.content})
        if r.stop_reason == "end_turn":
            return "".join(b.text for b in r.content if b.type == "text")
        if r.stop_reason == "tool_use":
            results = []
            for block in r.content:
                if block.type != "tool_use": continue
                try:
                    out = TOOL_IMPLS[block.name](block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)})
                except Exception as e:
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": json.dumps({"error": str(e)}), "is_error": True})
            messages.append({"role": "user", "content": results})
    raise RuntimeError("max iterations")
```

**Los detalles que importan**: `cache_control: ephemeral` marca el system prompt como cacheable (90% de descuento en reads, ~1.25× en writes; TTL 5min por defecto, 1h opt-in). Máximo **4 breakpoints** por request. Con caching activo, monitorea `usage.cache_read_input_tokens` para confirmar hit rate. Para retries: **backoff exponencial con jitter** respetando `retry-after` en 429; abortar en 4xx no-rate-limit; si usas orquestador durable (Temporal), setea `max_retries=0` en el SDK para evitar interferencia.

### 1.3 Subagentes en Claude Code — la mejor feature que no estás usando

Un subagente es **un Claude secundario invocado vía la tool `Agent`** (antes `Task`, renombrada en v2.1.63 — el alias sigue). **Contexto aislado**: tiene su propia ventana, system prompt y allowlist de tools. El padre solo recibe el **mensaje final** — toda la exploración intermedia no contamina el hilo principal.

Archivo `.claude/agents/code-reviewer.md`:

```yaml
---
name: code-reviewer
description: Expert code review specialist. Proactively reviews after writing or modifying code. Use immediately.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are a senior code reviewer. On invocation:
1. Run `git diff` to see recent changes
2. Review priority: bugs, security, duplicated code, error handling, tests
3. Output by severity: Critical / Warning / Suggestion with file:line + fix example
```

**Frontmatter completo** soporta: `tools` (allowlist), `disallowedTools` (denylist, se aplica antes), `model` (`sonnet`/`opus`/`haiku`/`inherit`), `permissionMode` (`plan`/`acceptEdits`/`bypassPermissions`), `maxTurns`, `skills`, `mcpServers` (exclusivos de este agente), `hooks` (scoped), `memory` (`user`/`project`/`local`), `isolation: worktree` (git worktree temporal), `effort`. Prioridad ante colisiones: **managed > CLI `--agents` > project > user > plugin**.

**Tres reglas críticas poco documentadas**: (1) los subagentes **no pueden spawnear otros subagentes** — anidación requiere `chain` desde el padre, Skills, o Agent Teams experimental (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`); (2) los permisos del padre **prevalecen** — si usas `bypassPermissions` en el padre, el hijo lo hereda sin poder bajarlo; (3) el `description` es **literalmente** el prompt de routing — frases como *"Use PROACTIVELY"* y *"Use immediately after..."* mejoran significativamente la auto-delegación.

**Sweet spot de subagentes**: tareas que (a) producen output verboso desechable (tests, log crunching, research), (b) requieren tool restrictions estrictas, (c) se paralelizan bien. **Antipatrón**: subagente para refactors simples de 3-5 archivos — el boot overhead supera el beneficio.

### 1.4 Los cinco patrones multi-agente que importan

Del cookbook oficial (`github.com/anthropics/claude-cookbooks/tree/main/patterns/agents`):

**Orchestrator-workers** (usar cuando no conoces N subtareas a priori): orquestador Opus/Sonnet descompone en N workers Haiku paralelos, sintetiza. Anthropic reporta **+90.2%** sobre single-agent Opus 4 en su sistema de research interno — **a costa de ~15× más tokens**. Solo justificable cuando el valor del output es alto y la tarea es breadth-first (research, code archaeology); catastrófico para coding con dependencias fuertes entre subtareas.

**Parallelization-voting**: N generaciones concurrentes → agregador (consenso, best-of-N, evaluator LLM). Útil para security review (pocos falsos negativos aceptables), moderación, decisiones de alto riesgo.

**Sequential pipeline**: cada step validado por gate programático antes de avanzar. Intercambia latencia por precisión.

**Evaluator-optimizer loop**: generator + evaluator con rúbrica, itera hasta que el evaluator aprueba. **Requiere criterios de evaluación claros** y que el LLM pueda articular feedback útil — si no se cumplen, es un anti-patrón que quema tokens.

**Routing**: classifier LLM (o clásico) decide qué modelo/prompt específico. Combinado con multi-tier (Haiku para volumen, Sonnet para lógica, Opus para arquitectura) ahorra ~80% de costo manteniendo calidad.

**Lección real del sistema de research de Anthropic**: el Lead agent **guarda su plan en disco inmediatamente** para sobrevivir al truncado >200k. Construyeron un *tool-testing agent* que prueba tools, detecta fallos del modelo y **reescribe la descripción del tool** — redujo completion time ~40%.

### 1.5 Claude Code subagents vs Devin vs Windsurf Cascade

| Dimensión | **Claude Code** | **Devin** | **Windsurf Cascade** |
|---|---|---|---|
| Runtime | Tu máquina (o remota via SDK) | Cloud sandbox VM (Ubuntu) | Tu IDE local |
| Multi-agente nativo | ✅ `.claude/agents/` + Agent Teams | Parcial (planner+executor interno) | No expuesto |
| Context isolation | ✅ por subagente | ✅ por sesión VM | ❌ único flow |
| Autonomía larga | Media (humano en loop) | **Alta** (horas autónomas) | Baja (interactivo) |
| Control fino | **Alto** (hooks, allowlists, permissionMode) | Bajo | Medio |
| Predictibilidad coste | Media (tokens visibles) | **Baja** (ACU opaco) | Alta |
| Paralelismo | ✅ worktrees + background | ✅ sesiones paralelas | Limitado (race conditions) |
| Transparencia | **Alta** (JSONL transcripts) | Media (replay UI post-hoc) | Alta (diffs inline) |

**Devin** (Cognition, $20 Core / $500 Team / 1 ACU ≈ 15min ≈ $2.25) brilla en **tareas async delegables y bien-scopeadas**: migraciones masivas (Nubank reporta ~20× ahorro), dep upgrades, bugfixes junior-level. **Falla** en tareas ambiguas, tooling interno no estándar, codebases spaghetti. El análisis de Answer.AI (enero 2025): **14 fracasos / 3 éxitos / 3 inconclusos en 20 tareas reales**. Devin 2.0/3.0 mejoran, pero Cognition **dejó de publicar SWE-bench oficial desde 2024** argumentando que "no representa la experiencia real" — lectura caritativa: honestidad; lectura crítica: los números no compiten con frontier (Claude Opus 4.5 ~80.9% SWE-bench Verified).

**Windsurf** (ahora parte de Cognition tras adquisición jul 2025; su equipo fundador se fue a Google DeepMind en reverse-acquihire de $2.4B) diferencia con **Flow Awareness**: rastrea edits, terminal, clipboard, navegación en tiempo real sin re-prompting. SWE-1.5 servido vía Cerebras a **950 tok/s** es genuinamente rápido. **Debilidades reales**: tab completion reportadamente poco fiable; pricing de créditos opaco con multiplicadores de modelo; turbulencia de roadmap post-acquisition; SWE-1.5 ronda 40% en SWE-Bench Pro vs 55-56% de Codex/Opus.

**Recomendación concreta**: mantén Claude Code como primary; prueba Windsurf si trabajas 80% en IDE con browser previews; Devin **solo si tienes backlog async delegable y puedes tolerar 40-60% success rate**. El patrón ganador en equipos senior es Claude Code (foreground judgment) + Devin (background bulk).

---

## 2. Skills — progressive disclosure como arquitectura

Skills es el feature más importante que Anthropic lanzó en 2025 (anunciado **16-oct-2025**, estándar abierto desde **18-dic-2025**, adoptado por OpenAI en feb 2026). El repo `anthropics/skills` tiene ~119k stars a abril 2026. **Simon Willison sostiene que son "bigger deal than MCP"** — y el dato empírico lo respalda: un skill es un directorio con un `SKILL.md`; MCP es hosts/clients/servers/3 transports/resources/prompts/tools/sampling/roots/elicitation. La simplicidad *es* el feature.

### 2.1 Progressive disclosure — los tres niveles

| Nivel | Cuándo | Coste | Contenido |
|---|---|---|---|
| **1. Metadata** | Siempre al iniciar sesión | ~100 tok/skill | `name` + `description` del frontmatter |
| **2. Body** | Cuando la skill se dispara | <5k tokens | Cuerpo completo de SKILL.md |
| **3. Resources/scripts** | Bajo demanda vía bash | Efectivamente ilimitado | Archivos referenciados, scripts (ejecutados, no leídos) |

El sistema construye dinámicamente la descripción de un meta-tool "Skill" agregando nombres+descripciones de todas las skills instaladas. Cuando el modelo decide usarla, ejecuta `bash cat skill-dir/SKILL.md` → nivel 2 entra a contexto. Esto te permite tener **decenas de skills sin inflar el contexto base**.

### 2.2 Anatomía canónica

```
my-skill/
├── SKILL.md              # REQUERIDO — frontmatter YAML + markdown
├── references/           # Docs organizados por dominio (lazy)
│   └── api-patterns.md
├── assets/               # Templates estáticos
│   └── pr-template.md
└── scripts/              # Código ejecutable (Python/Bash/JS)
    └── validate.py
```

Frontmatter mínimo:

```yaml
---
name: create-pr                   # lowercase, hyphens, ≤64 chars
description: >                    # ≤1024 chars, 3ª persona, qué + cuándo
  Creates a pull request following team conventions: runs tests, writes
  conventional commit, generates structured PR body, opens via gh CLI.
  Use when the user says "create a PR", "ship this", or has staged changes.
---
```

**Campos exclusivos Claude Code**: `allowed-tools`, `disable-model-invocation` (solo usuario invoca), `paths` (glob filter), `context: fork` + `agent: Explore` (ejecutar en subagente isolado), `model`, `effort`, `hooks`.

### 2.3 Cómo escribir descriptions que Claude *realmente* invoca

El skill-creator oficial de Anthropic recomienda **lenguaje "pushy"** porque Claude tiende a under-trigger. Tres reglas de oro: **tercera persona siempre** (la descripción se inyecta en system prompt; POV inconsistente rompe discovery); **patrón obligado qué+cuándo** (`"Generate commit messages by analyzing diffs. Use when user asks for commit messages or reviewing staged changes"`); **front-load keywords literales** que el usuario mencionaría (extensiones, nombres de tools, frases exactas).

**Target técnico**: body <500 líneas, description 200-400 chars, metadata total <100 tok por skill. Claude Code **no re-lee SKILL.md en turnos siguientes** — si lo editas mid-sesión, hay que re-invocar.

### 2.4 Ubicaciones y precedencia

Enterprise (managed) **>** Personal (`~/.claude/skills/`) **>** Project (`.claude/skills/` — committeable) **>** Plugin. `/mnt/skills/public/` contiene las 17 skills oficiales (pdf, docx, xlsx, pptx, skill-creator, mcp-builder, webapp-testing, etc.). **Live change detection** watchea todos los directorios — añadir/editar skills surte efecto sin reiniciar. Si una skill y un slash command comparten nombre, **la skill gana**.

En Claude Code a partir de 2026, **slash commands y skills se fusionaron**: un `.md` en `.claude/commands/` y un skill de un solo archivo son equivalentes funcionalmente. Migra a skills para poder añadir scripts/assets después.

### 2.5 Skills vs slash commands vs MCPs vs subagents

| Criterio | **Skills** | **Slash Commands** | **MCPs** | **Subagents** |
|---|---|---|---|---|
| Coste baseline | ~100 tok/skill | Solo nombre | **Alto** (schemas siempre) | 0 hasta spawn |
| Invocación | Auto semantic + `/name` | Manual `/name` (o auto) | Auto por modelo | Delegación vía Agent tool |
| Ejecuta código | Sí (scripts bundled) | Sí (via prompt) | Sí (server-side) | Sí (tools completas) |
| Context isolation | No | No | No | **Sí** (fork) |
| Portabilidad | Alta (estándar abierto) | Claude-specific | Media (requiere MCP client) | Claude Code-specific |

**Regla práctica**: MCPs son el **mayor generador de context bloat hoy**. Scott Spence documentó 66k tokens antes del primer prompt con 4 servers; reportes oficiales muestran warnings tipo *"Large MCP tools context (~81,986 tokens > 25,000)"*. Con `ENABLE_TOOL_SEARCH=auto:5`, Claude carga tool defs on-demand — reducción reportada del **46.9%**. Pero la mejor mitigación es elegir: CLI tools (`gh`, `aws`, `sentry-cli`) consumen menos contexto que MCPs equivalentes y suelen bastar.

---

## 3. MCP — del wire protocol al server en 80 líneas

**Spec vigente: `2025-11-25`**, liberada en el primer aniversario de MCP. Governance formal vía SEPs (*Specification Enhancement Proposals*) desde julio 2025; ~58 maintainers, 2.900+ contributors. Inspiración: Language Server Protocol, pero para LLMs.

### 3.1 Wire protocol — JSON-RPC 2.0 sobre transporte

```json
// Handshake paso 1: client → server
{"jsonrpc":"2.0","id":1,"method":"initialize",
 "params":{"protocolVersion":"2025-11-25",
           "capabilities":{"roots":{"listChanged":true},"sampling":{},
                           "elicitation":{"form":{},"url":{}}},
           "clientInfo":{"name":"MyClient","version":"1.0.0"}}}

// Paso 2: server → client con sus capabilities
{"jsonrpc":"2.0","id":1,"result":{
  "protocolVersion":"2025-11-25",
  "capabilities":{"tools":{"listChanged":true},
                  "resources":{"subscribe":true,"listChanged":true},
                  "prompts":{"listChanged":true}},
  "serverInfo":{"name":"MyServer","version":"1.0.0"}}}

// Paso 3: client → server (notification, sin id)
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

Tres tipos de mensaje: **request** (con `id`), **response** (con `id` matching), **notification** (sin `id`, fire-and-forget). La request `initialize` **no puede** ir en batch JSON-RPC. `id` nunca `null` y único por sesión.

### 3.2 Transports — trade-offs reales

| Transport | Conexión | Uso | Trade-offs |
|---|---|---|---|
| **stdio** | Child process, JSON-RPC por stdin/stdout, logs a stderr | Servers locales (filesystem, git) | ✅ Simple, sin auth. ❌ Una instancia por cliente, sin multiplexing |
| **Streamable HTTP** | `POST /mcp` + opcional SSE; sesiones via `Mcp-Session-Id` header | Servers remotos, SaaS | ✅ Session resumption con `Last-Event-ID`, OAuth 2.1 nativo, horizontal scaling ✅ Estándar desde 2025-11-25. ❌ Más complejo |
| **HTTP+SSE** (legacy) | Dos endpoints `/sse`+`/message` | Solo compat | **Deprecated** — reemplazado por Streamable HTTP |

**Regla crítica para stdio**: logs **DEBEN** ir a stderr, nunca stdout (corrompe el canal JSON-RPC). `console.error` en TS, `logging` con stream stderr en Python.

### 3.3 Componentes — lo que expone tu server

**Tools** (funciones ejecutables por el LLM): `tools/list` retorna `[{name, description, inputSchema, outputSchema?}]`; `tools/call` retorna `{content: [{type:"text"|"image"|"resource", ...}], isError?}`. Anotación útil: `_meta["anthropic/maxResultSizeChars"]: 200000`.

**Resources** (datos leíbles con URI): scheme libre (`file://`, `git://`, `postgres://`, custom). Soporta `subscribe` para `notifications/resources/updated`. En Claude Code se consumen con `@server:uri`.

**Prompts** (templates parametrizables): invocados por el **usuario**, no el LLM. En Claude Code aparecen como `/mcp__servername__promptname arg1 arg2`.

**Sampling** (server → client): el server pide al host que invoque al LLM, permitiendo servers agentic sin embeber su propia API key. **SEP-1577 (2025-11-25)** añadió `tools` y `toolChoice` dentro de sampling → loops agentic completos desde el server.

**Roots** (client capability): el cliente declara qué filesystem roots puede tocar el server. No enforced por protocolo — convención.

**Elicitation** (server pide input): form mode (JSONSchema) y **URL mode nuevo en 2025-11-25 (SEP-1036)** para OAuth/payment out-of-band sin que el cliente vea los tokens.

**Tasks** (experimental 2025-11-25): async tasks con estados `working | input_required | completed | failed | cancelled`. Útil para research/migration tools de minutos-horas.

### 3.4 Server TypeScript completo — stdio

```typescript
// npm i @modelcontextprotocol/sdk zod
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer(
  { name: "demo-server", version: "1.0.0" },
  { instructions: "Demo server: `add` suma, `greeting://{name}` saluda, prompt `code_review`." }
);

server.registerTool("add",
  { title: "Addition", description: "Suma dos enteros.",
    inputSchema: { a: z.number(), b: z.number() } },
  async ({ a, b }) => ({ content: [{ type: "text", text: String(a + b) }] })
);

server.registerResource("greeting",
  new ResourceTemplate("greeting://{name}", { list: undefined }),
  { title: "Greeting", description: "Saludo personalizado", mimeType: "text/plain" },
  async (uri, { name }) => ({ contents: [{ uri: uri.href, text: `Hola, ${name}!` }] })
);

server.registerPrompt("code_review",
  { title: "Code Review", description: "Revisar snippet",
    argsSchema: { language: z.string(), code: z.string() } },
  ({ language, code }) => ({ messages: [{ role: "user", content: { type: "text",
    text: `Revisa este código ${language}:\n\n\`\`\`${language}\n${code}\n\`\`\`` }}] })
);

await server.connect(new StdioServerTransport());
```

Para Streamable HTTP: reemplaza el transport por `StreamableHTTPServerTransport` + Express con handlers `POST/GET/DELETE /mcp`.

### 3.5 Server Python con FastMCP

```python
# pip install "mcp[cli]"
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Suma dos enteros."""
    return a + b

@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    return f"Hola, {name}!"

@mcp.prompt()
def code_review(language: str, code: str) -> str:
    return f"Revisa este código {language}:\n\n```{language}\n{code}\n```"

if __name__ == "__main__":
    mcp.run(transport="stdio")  # o "streamable-http"
```

**Testing obligatorio antes de integrar en Claude Code**: `npx @modelcontextprotocol/inspector npx tsx src/server.ts` abre UI en localhost:6274 con request/response JSON-RPC crudo. Evita bucles infinitos de debugging desde Claude Code.

### 3.6 Integración en Claude Code

```bash
# Comando básico — OJO: flags antes del nombre, -- separa el subcomando
claude mcp add --transport stdio --scope project demo -- npx tsx src/server.ts

# HTTP remoto con OAuth
claude mcp add --transport http github https://api.githubcopilot.com/mcp/ \
  -H "Authorization: Bearer $GITHUB_PAT"

# Desde JSON crudo
claude mcp add-json weather-api '{"type":"http","url":"https://api.weather.com/mcp"}'

# Debug
/mcp                        # estado: connected/failed/pending dentro de la sesión
MCP_TIMEOUT=10000 claude    # amplía arranque
```

`.mcp.json` (commit en proyecto) soporta `${VAR}` / `${VAR:-default}` expansion en `command`, `args`, `env`, `url`, `headers`:

```json
{
  "mcpServers": {
    "db": {"type": "stdio", "command": "npx",
           "args": ["-y", "@bytebase/dbhub", "--dsn", "${DATABASE_URL}"]},
    "api": {"type": "http", "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer ${API_KEY}"},
            "oauth": {"clientId": "abc123", "scopes": "read write"}}
  }
}
```

**Scopes**: `local` (default, privado, `~/.claude.json`) > `project` (`.mcp.json` versionado, **requiere aprobación** al primer uso) > `user` (global). `claude mcp reset-project-choices` revoca aprobaciones.

### 3.7 Seguridad MCP — las diez amenazas reales

**Taxonomía de ataques documentados**: prompt injection indirecto (resources externos con instrucciones); tool poisoning (descripción maliciosa en `tools/list`); rug pull (server legítimo cambia descripciones post-approval); tool shadowing (nombres similares a tools trusted); confused deputy (server con credenciales amplias actúa fuera del usuario); data exfiltration via side-channel; session hijack; **RCE via mcp-remote (CVE-2025-6514)**; excessive scopes; supply chain via `npx -y unknown-package`.

**Mitigaciones production**: TLS siempre; fine-grained OAuth scopes pineados; short-lived tokens con DPoP/mTLS; tool allowlisting org-wide vía `managed-mcp.json` (macOS: `/Library/Application Support/ClaudeCode/managed-mcp.json`); sandboxing stdio servers en containers sin acceso a `~/.ssh`/`~/.aws`; input validation estricta (Zod/Pydantic); logging centralizado de tool calls; **pin tool defs por hash** y re-prompt si cambian; **nunca** auto-approve tool calls en flujos autónomos.

**Windsurf MCP** comparación: soporta MCP nativamente desde 2025 vía `~/.codeium/windsurf/mcp_config.json`. Diferencias: **no tiene scope project** committeable (team sharing vía registries privados Enterprise); **límite duro de 100 tools concurrentes**; permite `alwaysAllow: [...]` array per-server (Claude Code solo tiene per-server, no per-tool). JetBrains IDEs 2025.2+ van al revés: el **IDE mismo es un MCP server** que otros clientes consumen.

---

## 4. Hooks — determinismo fuera del LLM

Los hooks son **shell commands, HTTP, o prompts LLM** que disparan en eventos del ciclo de vida de Claude Code. Son el mecanismo para **garantizar** que algo ocurra — no depender del LLM para formateo, validación o policy.

### 4.1 Eventos del ciclo de vida (v2.1+)

Los más usados: `SessionStart` (matchers: `startup`/`resume`/`clear`/`compact`), `UserPromptSubmit` (puede inyectar contexto), `PreToolUse` (puede bloquear con exit 2 o `permissionDecision: deny`; desde v2.0.10 puede modificar input con `updatedInput`), `PostToolUse` (ideal para format/lint, no deshace ejecución), `Notification`, `SubagentStart/Stop`, `Stop` (cuidado con loops — siempre chequea `stop_hook_active`), `PreCompact/PostCompact`, `PermissionRequest`, `InstructionsLoaded`, `FileChanged`, `WorktreeCreate/Remove`, `Elicitation` (v2.1.76+ para auto-respuesta a MCP elicitations).

**Gotcha crítico**: `PermissionRequest` **no dispara en modo headless** (`-p`). Usa `PreToolUse` como alternativa.

### 4.2 Configuración — settings.json

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write|MultiEdit",
      "hooks": [{
        "type": "command",
        "command": "jq -r '.tool_input.file_path' | xargs -I{} sh -c 'case \"{}\" in *.py) ruff format \"{}\" && ruff check --fix \"{}\" ;; *.ts|*.tsx|*.js|*.jsx) npx prettier --write \"{}\" ;; esac'",
        "timeout": 30
      }]
    }],
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{"type": "command",
                 "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bash-guard.sh"}]
    }]
  }
}
```

Precedencia: **managed > `.claude/settings.json` (proyecto, committeable) > `.claude/settings.local.json` (gitignored) > `~/.claude/settings.json`**. Plugin hooks en `plugins/<name>/hooks/hooks.json`.

**Control de decisiones** vía exit codes o JSON estructurado:
- Exit `0` → permitir; stdout de `SessionStart`/`UserPromptSubmit` se inyecta a contexto.
- Exit `2` → bloquear; stderr va a Claude como feedback → **Claude se auto-corrige**.
- JSON estructurado por stdout con `permissionDecision: "deny" | "allow" | "ask" | "defer"` y `permissionDecisionReason`.

Un hook `deny` bloquea **incluso bajo `--dangerously-skip-permissions`** — el único mecanismo que usuarios no pueden sortear. Los `allow`, en cambio, **no sobrescriben** deny rules de settings.

### 4.3 Los hooks que todo repo profesional debería tener

**1. Auto-format post-edit** (arriba en §4.2).

**2. Bloqueo de comandos peligrosos** (`.claude/hooks/bash-guard.sh`):

```bash
#!/bin/bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command')
DANGEROUS='(rm -rf /|:(){ :|:& };:|DROP TABLE|mkfs\.|dd if=.*of=/dev/|curl .* \| (sh|bash))'
if echo "$CMD" | grep -qE "$DANGEROUS"; then
  cat <<EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Comando bloqueado por política."}}
EOF
fi
```

**3. Stop hook anti-loop** — *siempre* con guard:

```bash
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then exit 0; fi
```

**4. Audit trail** (`PostToolUse` + `UserPromptSubmit` → JSONL a disk o HTTP a audit server).

**5. SessionStart post-compact**: re-inyecta recordatorios de stack y rama actual.

**Seguridad crítica**: los hooks committeados en `.claude/settings.json` **se ejecutan sin confirmación** al abrir el proyecto. Son **vector de ataque** — revisa hooks de repos ajenos antes de clonar. Managed settings admin-level pueden bloquear overrides con `disableBypassPermissionsMode`.

---

## 5. Herramientas adicionales — slash commands, CLAUDE.md, memory, plan mode, headless, checkpoints

### 5.1 Slash commands — el sucesor es Skills

Archivo `.claude/commands/commit.md`:

```markdown
---
description: Stage y crea commit con conventional commits
argument-hint: [scope opcional]
allowed-tools: Bash(git add:*), Bash(git diff:*), Bash(git commit:*)
---

## Contexto
- Status: !`git status --short`
- Staged diff: !`git diff --cached`

## Tarea
1. Propón mensaje Conventional Commits con scope `$ARGUMENTS`
2. Ejecuta `git commit` (sin `Co-authored-by: Claude`)
3. NO pushees
```

Frontmatter: `allowed-tools` (pre-aprueba), `description`, `argument-hint`, `model`, `disable-model-invocation`. Argumentos: `$ARGUMENTS` (todo), `$1`-`$N` (posicionales). Referencias: `@path` incluye contenido, `` !`cmd` `` ejecuta shell antes del prompt. Subdirectorios crean namespaces: `.claude/commands/db/migrate.md` → `/db:migrate`.

**En 2026 commands y skills se fusionaron**: `.claude/commands/foo.md` y `.claude/skills/foo/SKILL.md` son funcionalmente equivalentes. Migra a skills cuando necesites scripts/assets auxiliares o auto-invocación semántica.

### 5.2 CLAUDE.md — hierarchical memory

Jerarquía de precedencia (mayor → menor): **enterprise managed policy > project (`./CLAUDE.md` o `.claude/CLAUDE.md`) > user (`~/.claude/CLAUDE.md`) > CLAUDE.local.md** (*deprecado* — migra a `@~/.claude/...` imports que funcionan mejor con worktrees).

Imports con `@path` soportan recursión hasta profundidad 5, paths relativos/absolutos incluido `~/`, no se evalúan en code blocks (seguro documentar sintaxis), imports a ubicaciones externas piden aprobación la primera vez.

**Monorepo — patrón jerárquico real**:

```
monorepo/
├── CLAUDE.md                   # universal, <200 líneas
├── .claude/
│   ├── settings.json           # hooks compartidos
│   ├── commands/               # globales
│   └── rules/
│       └── testing.md          # con paths: ['packages/**'] en frontmatter
├── packages/
│   ├── api/
│   │   ├── CLAUDE.md           # específico package
│   │   └── .claude/commands/scaffold-route.md
│   └── web/
│       └── CLAUDE.md
```

**Limitación conocida (#37344)**: hooks, MCP servers y settings en `.claude/` anidados **no se auto-descubren** desde la raíz — solo skills y CLAUDE.md. Para hooks por package desde una sesión lanzada en raíz: usa matcher por path en el hook root con script que detecta directorio y aplica formatter correspondiente.

**Anti-patrones reales**: CLAUDE.md >500 líneas (adherencia decae drásticamente; target <200); contradicciones entre niveles; info time-sensitive ("usa API v1 hasta agosto"); duplicación del README en lugar de `@README.md`. **CLAUDE.md es sugerencia, no enforcement** — para hard rules usa hooks.

### 5.3 Memory — dos sistemas distintos

**Memory tool de la API** (beta header `context-management-2025-06-27`, tool `memory_20250818`, lanzada sept 2025): es client-side — el modelo emite `tool_use` con comandos `view/create/update/delete` sobre un directorio `/memory`, y **tu aplicación ejecuta las ops localmente** (filesystem, DB, S3, vector store). No está integrado en Claude Code CLI — solo vía SDK.

**`/memory` en Claude Code**: abre CLAUDE.md en tu editor. No es el memory tool de la API. Combínalo con `/init` (escanea repo y genera CLAUDE.md inicial) y con `#` inline (prefijar una línea con `#` añade regla al CLAUDE.md apropiado).

**Auto memory**: notas en `~/.claude/projects/<proyecto>/memory/` que Claude escribe durante sesiones y recarga al inicio. Subagentes tienen su propia auto memory.

### 5.4 Plan mode — read-only agéntico

Activación: `Shift+Tab` cicla Edit → Auto-Accept → Plan → Edit; o `/plan`; o arrancar con `claude --permission-mode plan`. Windows en algunas versiones requiere `Alt+M`.

El análisis interno de Armin Ronacher (dic 2025) revela que plan mode **no desactiva tools de escritura físicamente** — el agente tiene acceso pero recibe system reminders recurrentes de read-only. Internamente es una tool (`ExitPlanMode`) que Claude puede auto-invocar. El plan generado es un markdown file que Claude edita con su Edit tool. Activa el subagente **Explore** (Haiku-based) automáticamente para búsquedas → ahorro de tokens en main context.

**Workflow recomendado** (Boris Cherny): Plan mode → iterar plan → `Ctrl+G` abre plan en editor para modificar → Shift+Tab a Auto-Accept → ejecutar.

### 5.5 Headless / SDK — automatización programable

```bash
claude -p "Find and fix SQL injection in auth.py" \
  --allowedTools "Read,Edit,Bash" \
  --permission-mode acceptEdits \
  --output-format json \
  --bare \
  --max-turns 20

# Con JSON schema forzando structured output
claude -p "Extract function names" --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}'
```

Flags clave: `--output-format text|json|stream-json`, `--resume <session-id>` / `--continue`, `--allowedTools` / `--disallowedTools`, `--append-system-prompt`, `--mcp-config servers.json`, `--agents '{...}'`, `--bare` (recomendado para scripts/CI, será default), `--debug-file`.

**Claude Agent SDK** (rebrand sept 2025 de Claude Code SDK): `@anthropic-ai/claude-agent-sdk` (npm) / `claude-agent-sdk` (pip). Features sobre CLI puro: tool approval callbacks programáticos, message objects tipados, `createSdkMcpServer` para tools MCP in-process, streaming nativo, sesiones multi-turno.

```python
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    opts = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash"],
        permission_mode="acceptEdits",
        system_prompt_append="Focus on security."
    )
    async for message in query(prompt="Fix SQL injection in db.py", options=opts):
        print(message)

anyio.run(main)
```

**GitHub Actions oficial** (`anthropics/claude-code-action@v1`): activación por mentions `@claude` en issues/PRs o `direct_prompt`. Para CI non-interactive: `--bare` evita leer config local del runner, `actions/cache@v4` con `~/.claude`, fallback soft con `|| echo skip`.

### 5.6 Checkpoints — el feature más infravalorado de Claude Code 2.0

Lanzado sept 2025. Automático antes de cada edit: snapshot de archivos + conversación. Trigger con `Esc Esc` o `/rewind`. UI muestra lista scrollable de prompts pasados. **Tres modos de restore**: code+conversation (reset total), conversation only (mantiene código, vuelve chat — útil cuando el código está bien pero la conversación fue por tangente), code only (revierte archivos, mantiene chat para probar approach alternativo). Retención 30 días.

**Limitaciones críticas**: solo trackea edits vía tools de Claude — archivos modificados por `rm`/`mv`/`cp` en Bash **no se revierten**. No reemplaza git. Solo archivos tocados en la sesión actual.

Workflow: plan mode → iterar → exit plan acceptEdits → Claude implementa 10 archivos → no te gusta el approach → `Esc Esc` → "Restore code and conversation" al prompt inicial → re-prompt con approach alternativo.

---

## 6. Decisión y composición — qué usar cuándo

### 6.1 Tabla comparativa de las seis primitivas

| Criterio | **CLAUDE.md** | **Slash cmd** | **Skill** | **MCP** | **Hook** | **Subagent** |
|---|---|---|---|---|---|---|
| Coste contexto baseline | Alto (permanente) | 0 hasta invocar | ~100 tok (metadata) | Medio-alto (tool names) | 0 | 0 hasta spawn |
| Invocación | Siempre cargado | Manual `/x` | Auto semántica + `/x` | Auto por modelo | Por evento | Delegación |
| Determinismo | Bajo (depende del LLM) | Bajo | Bajo | Medio (tool específica) | **Alto** | Bajo |
| Enforcement | No | No | No | No | **Sí** | No |
| Context isolation | No | No | No | No | N/A | **Sí** |
| Composable con otros | ✅ imports | ✅ llama skills/agents | ✅ invoca MCPs, spawns agents | ✅ | ✅ prompt/agent hooks | ✅ carga skills |
| Portabilidad | Repo | Repo | **Estándar abierto cross-vendor** | Estándar MCP cross-vendor | Repo | Claude-specific |

### 6.2 Tabla de decisión "si quiero X, uso Y"

| Quiero... | Uso |
|---|---|
| Convenciones que Claude sepa siempre | **CLAUDE.md** |
| Guía de estilo solo al tocar endpoints | **Skill** con `paths: ['src/api/**']` |
| Atajo para prompt repetido | **Slash command** |
| Leer DB interna / API corporativa | **MCP** |
| Formatear código después de cada edit | **Hook PostToolUse** |
| Bloquear `rm -rf`, edits a `.env` | **Hook PreToolUse** |
| Review de PR con contexto limpio | **Subagente** |
| 3 revisores paralelos (sec, perf, tests) | **Agent team** (experimental) |
| Compartir config entre repos | **Plugin** que empaqueta todo |
| Gate de calidad en CI | `claude -p` headless + exit codes |
| Docs ADR accesibles | **Skill** + `@docs/adr/` |

### 6.3 Arquitectura end-to-end — cómo se componen

```
       dev prompt
            │
            ▼
   [SessionStart hook] ──── injects recent ADRs, sprint issues
            │
            ▼
   CLAUDE.md + skill descriptions (~100 tok/skill) + MCP tool names
            │
     ┌──────┼──────────┬──────────────┐
     ▼      ▼          ▼              ▼
  Read    Load       MCP:           Spawn subagent
  files   SKILL      Postgres       "research-cache"
          (body)     query schema   (isolated ctx)
     │      │          │              │
     └──────┴──────────┴──────────────┘
            │
            ▼
   Plan → Edit files
            │
            ▼  (cada Edit dispara)
   [PostToolUse hook] ─── ruff + pyright; exit 2 → Claude self-corrects
            │
            ▼
   Run tests (Bash) ─── [PreToolUse] valida comando OK
            │
            ▼
   Spawn subagent "pr-reviewer" ─── review con contexto fresco
            │
            ▼
   gh CLI abre PR con conventional commit
            │
            ▼
   [Stop hook] ─── métricas a Langfuse
```

**Regla de composición crítica**: separa *inspiración* (CLAUDE.md, skills) de *enforcement* (hooks, CI). No confíes en "please follow X" para cosas críticas. Rules para sugerir + hooks para validar + CI como última línea.

---

## 7. Integrar IA en un repo existente

### 7.1 Setup progresivo con triggers claros

**Escala solo cuando aparece el trigger** — Anthropic oficial:

| Trigger | Añadir |
|---|---|
| Claude equivoca la misma convención 2 veces | línea en **CLAUDE.md** |
| Repites el mismo prompt inicial | **slash command** o **skill** |
| Pegas el mismo playbook 3ª vez | **skill** con scripts |
| Copias datos de sistema externo | **MCP** |
| Un sub-task llena el contexto con output desechable | **subagente** |
| Algo debe pasar "siempre, sin excepciones" | **hook** |
| Un segundo repo necesita lo mismo | **plugin** |

**Orden recomendado absoluto**: CLAUDE.md → slash commands → skills → hooks → MCPs → subagents. Los MCPs al final porque son el mayor generador de context bloat y hay que haberlos necesitado antes de añadirlos.

### 7.2 Antipatrones reales — lectura crítica

**CLAUDE.md dumping ground de 2000 líneas**: Anthropic docs oficial lo confirma — *"bloated CLAUDE.md files cause Claude to ignore your actual instructions"*. Target <200 líneas. Aplica test de eliminación: *"si borro esta línea, ¿Claude cometerá un error?"* — si no, fuera.

**MCP fatigue**: Scott Spence documentó 66k+ tokens antes del primer prompt. Reddit users reportan 67k por 4 servers. Warning oficial *"Large MCP tools context (~81,986 tokens > 25,000)"*. Mitigación real: `ENABLE_TOOL_SEARCH=auto:5` (46.9% reducción reportada), `.mcp.json` project-scoped en vez de user-global, `/mcp` para auditar coste por servidor.

**Hooks que bloquean demasiado**: si el equipo empieza a añadir `--no-verify` o mueve trabajo a `settings.local.json` para avanzar, tus hooks están rotos. Hooks PreToolUse deben ser <2s. Mensaje stderr debe ser accionable (*"run `pnpm format` to fix"*). Empieza con warnings (exit 0 + message), no con bloqueos. Mide: >5 bloqueos/dev/día = demasiado.

**Agent fatigue**: 15 agents con descripciones solapadas (`code-reviewer` + `reviewer` + `security-reviewer`). Regla: si la tarea lee <10 archivos que reusarás, inline. Solo crea subagente si hay aislamiento real o paralelismo.

**Permission deny con bypasses conocidos**: `Read(.env)` denied en settings, pero `cat .env` via Bash bypassa. Refuerza con hook PreToolUse Bash.

**Kitchen sink sessions**: no usar `/clear` entre tareas no relacionadas. Si corriges el mismo issue 3+ veces, `/clear` y re-prompt con lo aprendido.

### 7.3 Métricas y rangos realistas

| Métrica | Cómo medir | Target realista |
|---|---|---|
| PRs merged/dev/week uplift | GitHub analytics | 1.3-1.7× (Anthropic interno: +67%) |
| CI pass rate en primer push | % | 70-85% en repos AI-friendly |
| Cost/PR | usage / PRs merged | $15-50 incremental |
| % código AI-touched en PRs | Claude Code Analytics | 40-70% (Anthropic interno 70-90%) |
| Context usage antes del prompt | `/context` | <50% (>60% = bloat) |
| ROI value/cost | tracked | 3:1 a 5:1 en equipos maduros |

**Caveat honesto**: los números tope (67% uplift, 70-90% code by Claude) son **Anthropic sobre Anthropic**. En proyectos cliente típicos ronda 1.3-1.5× con cultura establecida, 2× solo con inversión fuerte en setup.

### 7.4 Casos prácticos — setups concretos

**Frontend Next.js**: CLAUDE.md con reglas App Router ("Server Components by default; Client only with 'use client' + razón comentada"; "NEVER useEffect for data fetching — use Server Components o TanStack Query"). Hook PostToolUse con Prettier auto. Skill `rsc-patterns` con referencia local a `node_modules/next/dist/docs/`. Slash commands `/new-page`, `/new-component`.

**Backend Python/FastAPI**: reglas de capas estrictas ("No DB session en routers; dependencies via `Depends()`; domain exceptions separadas de HTTPException"). Hook PreToolUse Bash bloqueando `alembic downgrade`, `DROP TABLE`, `TRUNCATE`. MCP Postgres **solo en dev, desactivado en CI**. Skill `sqlalchemy-async` con pitfalls comunes.

**Monorepo Turborepo**: raíz CLAUDE.md con reglas cross-package y topología de dependencias (<150 líneas). Cada package con CLAUDE.md local + `packages/shared/CLAUDE.md` estricto marcado "HIGH IMPACT". Hook root detecta path y aplica formatter correspondiente. Plugin opcional empaquetando todo para el próximo cliente Turborepo.

**Librería publicable**: CLAUDE.md empieza con *"This is a PUBLISHED library. Every change affects users."* Rules duras: `src/index.ts` único punto de export; nunca exportar de `src/internal/`; cambios breaking requieren ADR + team sign-off + major bump; nunca remover públicos sin deprecation cycle. Hook PreToolUse Edit detectando cambios en `src/index.ts` o `package.json#exports` → exige confirmación explícita.

### 7.5 Evals — testing tu integración de IA

Herramientas por madurez: empezar con **prompts-as-tests versionados en el repo** (`claude -p` headless + 20 casos canary). Cuando el equipo crezca >5 devs o haya clientes exigiendo trazabilidad: **Langfuse** (open-source, OTEL, self-host; requiere Postgres + ClickHouse) o **Braintrust** (managed SaaS, Playground, CI/CD gating). Para costes/usage: `anthropics/claude-code-monitoring-guide` (Prometheus + OTEL + Grafana).

**Cadencia de revisión**: cada sprint revisa últimos 20 PR comments y errores recurrentes; cada release mayor audita CLAUDE.md por reglas obsoletas; cada quarter re-audita MCPs (`/mcp` token cost) y desconecta los no usados >30 días.

---

## 8. Conclusión y trade-offs honestos

El stack Claude Code en abril 2026 es **el más potente y controlable** del mercado, pero ese control exige disciplina. **El mayor riesgo hoy no es el modelo — es el context bloat**: MCPs mal elegidos inflan el contexto base a 60-80k tokens antes del primer prompt, CLAUDE.md de 2000 líneas se vuelven ruido ignorado, skills solapadas confunden el routing. La disciplina clave: **cada primitiva debe justificar su coste de contexto medible con `/context`**.

La convergencia de skills y slash commands, la apertura del estándar Skills (OpenAI adopción feb 2026), y la madurez de MCP 2025-11-25 con OAuth 2.1 nativo apuntan a que **el stack se está estabilizando** — decisiones de arquitectura que tomes hoy son razonablemente duraderas. La excepción son las features experimentales (Agent Teams, MCP Tasks, memory tool API) que evolucionarán en 6-12 meses; no las apuestes en producción crítica.

Respecto a competidores: **Windsurf** (turbulencia corporativa post-Google/Cognition; SWE-1.5 bajo frontier) y **Devin** (ACU pricing opaco, tasa de éxito impredecible ~40-60%, Cognition dejó de publicar SWE-bench desde 2024) tienen usos específicos pero no reemplazan Claude Code para dev senior con control granular. El patrón ganador emergente es **Claude Code + Devin complementarios**: foreground judgment + background bulk. Windsurf solo si específicamente quieres IDE visual con Flow Awareness, y aun así Cursor compite directamente.

El insight no obvio: **no necesitas frameworks**. La API de Anthropic + archivos markdown con frontmatter YAML + JSON-RPC 2.0 sobre stdio es todo. LangChain, CrewAI y abstracciones similares agregan complejidad sin valor medible sobre el código directo mostrado en la sección 1.2. El propio equipo de Anthropic martillea este punto en *Building effective agents*: **empieza simple, añade complejidad solo con mejora medible**. Tu implementación de 80 líneas será más debuggeable, más barata en tokens, y más mantenible que cualquier framework.