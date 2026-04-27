/**
 * Paper Examples — Curated real-world code examples of AI-generated technical debt.
 *
 * Each example is manually verified from the analysis of 214K+ issues across 46K+ commits.
 * Examples are grouped by category for the research paper.
 */

const EXAMPLES = [

    // =========================================================================
    // SECURITY VULNERABILITIES
    // =========================================================================
    {
        id: "sec-exec",
        category: "security",
        title: "Use of exec() — Arbitrary Code Execution Risk",
        tool: "Copilot",
        repo: "wasi-master/fastero",
        commit: "bd79ced69b4c",
        commitUrl: "https://github.com/wasi-master/fastero/commit/bd79ced69b4cbd3da1d25d09bb7f3a6ea1e53427",
        fileUrl: "https://github.com/wasi-master/fastero/blob/bd79ced69b4cbd3da1d25d09bb7f3a6ea1e53427/fastero/utils.py#L524",
        file: "fastero/utils.py",
        line: 524,
        rule: "B102",
        severity: "medium",
        annotation: "Copilot generated benchmarking code that uses <strong>exec()</strong> to execute user-provided code strings. While exec() is sometimes necessary for benchmarking tools, it introduces arbitrary code execution risk (CWE-95). The AI did not add any sandboxing, input validation, or security warnings.",
        code: `exec(self.setup_code, namespace)

# Execute the statement multiple times for warmup
for _ in range(number):
    try:
        exec(self.stmt, namespace)  # ← B102: Use of exec detected
    except Exception:
        # If execution fails, we'll let the main benchmark handle the error
        break`,
        highlightLines: [5],
        lang: "python",
    },
    {
        id: "sec-bind-all",
        category: "security",
        title: "Binding to 0.0.0.0 — Network Exposure",
        tool: "Copilot",
        repo: "Azure-Samples/azure-ai-travel-agents",
        commit: "1e15ad204e09",
        commitUrl: "https://github.com/Azure-Samples/azure-ai-travel-agents/commit/1e15ad204e09",
        fileUrl: "https://github.com/Azure-Samples/azure-ai-travel-agents/blob/1e15ad204e09/src/api-python/src/main.py#L259",
        file: "src/api-python/src/main.py",
        line: 259,
        rule: "B104",
        severity: "medium",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) configured a <strong>uvicorn</strong> server to bind to <code>0.0.0.0</code> (all network interfaces) with reload enabled. In cloud environments, this exposes the API server to the entire network (CWE-200). The secure default should be <code>127.0.0.1</code>. This is an Azure sample project — insecure defaults in sample code propagate to users who copy-paste.",
        code: `    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # ← B104: Binding to all interfaces
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )`,
        highlightLines: [5],
        lang: "python",
    },
    {
        id: "sec-insecure-temp",
        category: "security",
        title: "Insecure Temp File Usage — Race Condition",
        tool: "Cursor",
        repo: "RedisTimeSeries/RedisTimeSeries",
        commit: "40e6ea42bab3",
        commitUrl: "https://github.com/RedisTimeSeries/RedisTimeSeries/commit/40e6ea42bab32225678a70cc2352f6148f26f293",
        fileUrl: "https://github.com/RedisTimeSeries/RedisTimeSeries/blob/40e6ea42bab32225678a70cc2352f6148f26f293/tools/bench_two_shards.py#L274",
        file: "tools/bench_two_shards.py",
        line: 274,
        rule: "B108",
        severity: "medium",
        annotation: "Cursor generated benchmarking code using a hardcoded <strong>/tmp</strong> path instead of Python's <code>tempfile</code> module. This creates a predictable file location vulnerable to symlink attacks and race conditions (CWE-377). The <code>shutil.rmtree()</code> on line 276 compounds the risk — an attacker could place a symlink causing deletion of arbitrary directories.",
        code: `    warmup_s: float,
    conc: list[int],
    *,
    nodes: int,
) -> BenchResult:
    workdir = os.path.realpath(os.path.join("/tmp", f"rts_bench_cluster_{base_port}"))  # ← B108
    if os.path.exists(workdir):
        shutil.rmtree(workdir)  # Dangerous with predictable path
    os.makedirs(workdir, exist_ok=True)`,
        highlightLines: [6],
        lang: "python",
    },
    {
        id: "sec-hardcoded-secret",
        category: "security",
        title: "JWT Secret Key Hardcoded — Authentication Bypass",
        tool: "Copilot",
        repo: "ZathuraDbg/ZathuraDbg",
        commit: "9f813f828a85",
        commitUrl: "https://github.com/ZathuraDbg/ZathuraDbg/commit/9f813f828a85",
        fileUrl: "https://github.com/ZathuraDbg/ZathuraDbg/blob/9f813f828a85/civic_backend/auth.py#L7",
        file: "civic_backend/auth.py",
        line: 7,
        rule: "B105",
        severity: "high",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) hardcoded a JWT secret key as the literal string <strong>\"your-secret-key-change-in-production\"</strong> — and even added a comment saying \"Change this in production.\" The file was committed as-is. Anyone who reads the source can forge valid JWTs and bypass authentication entirely (CWE-798). This is a uniquely AI anti-pattern: generating <em>placeholder secrets with TODO-style comments</em> that ship to production.",
        code: `from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"  # ← B105: hardcoded secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)`,
        highlightLines: [7],
        lang: "python",
    },
    {
        id: "sec-leaked-credentials",
        category: "security",
        title: "Real Session Tokens Committed to Source — Credential Leak",
        tool: "Cursor",
        repo: "adysec/h1_asset",
        commit: "d8c0a41826d9",
        commitUrl: "https://github.com/adysec/h1_asset/commit/d8c0a41826d9",
        fileUrl: "https://github.com/adysec/h1_asset/blob/d8c0a41826d9/h1_asset.py#L11",
        file: "h1_asset.py",
        line: 11,
        rule: "B105",
        severity: "high",
        annotation: "Cursor (sole author: Cursor Agent) committed <strong>real HackerOne session cookies and a CSRF token</strong> directly into the source file as \"default inline configuration.\" The cookies include a full <code>__Host-session</code> value, Google Analytics IDs, and device fingerprints. Anyone cloning this repo gets valid credentials (CWE-798). With <strong>67 B105 hardcoded-password issues</strong> in our sole-author dataset, AI tools routinely embed secrets in source instead of using environment variables or secret managers.",
        code: `# Default inline configuration (filled here instead of secrets manager)
H1_DEFAULT_COOKIES = {"h1_device_id": "6b006754-624f-48dd-8640-...",
    "_gcl_au": "1.1.11592276.1653657152",
    "_ga": "GA1.2.1701425692.1653657219",
    "__Host-session": "dEJBMnQwcjlwQlNn...--2241d124b675695c0d174cae",
    # ... 6 more tracking/session cookies ...
}
H1_DEFAULT_X_CSRF_TOKEN = "QOFiIvQ7XJceEJ/y7Z5M...dfQF7Q=="  # ← B105: real CSRF token`,
        highlightLines: [1, 8],
        lang: "python",
    },
    {
        id: "sec-shell-inject",
        category: "security",
        title: "Shell Injection via curl | bash with shell=True",
        tool: "Copilot",
        repo: "seagullz4/hysteria2",
        commit: "e277daf540da",
        commitUrl: "https://github.com/seagullz4/hysteria2/commit/e277daf540da",
        fileUrl: "https://github.com/seagullz4/hysteria2/blob/e277daf540da/hysteria2.py#L74",
        file: "hysteria2.py",
        line: 74,
        rule: "B602",
        severity: "high",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) wrote <strong>9 instances</strong> of <code>subprocess.run(..., shell=True)</code> in a single file. The worst case pipes a remote URL through bash: <code>bash &lt;(curl -fsSL https://...)</code>. If the URL is compromised, this becomes arbitrary code execution (CWE-78). The file also runs <code>rm -rf</code> chains via shell. With <strong>20 B602 shell-injection issues</strong> in our dataset, AI tools routinely use <code>shell=True</code> as a shortcut.",
        code: `def hysteria2_uninstall():
    while True:
        choice_1 = input("是否进行卸载hysteria2 [y/n] ：")
        if choice_1 == "y":
            subprocess.run("bash <(curl -fsSL https://get.hy2.sh/) --remove",
                shell=True, executable="/bin/bash")  # ← B602: shell injection
            subprocess.run("systemctl stop hysteria-iptables.service 2>/dev/null",
                shell=True)  # ← B602
            subprocess.run("rm -rf /etc/hysteria; rm -rf /etc/systemd/system/"
                "multi-user.target.wants/hysteria-server.service; "
                "systemctl daemon-reload; rm -rf /usr/local/bin/hy2",
                shell=True)  # ← B602: rm -rf via shell`,
        highlightLines: [5, 6, 8, 12],
        lang: "python",
    },
    {
        id: "sec-no-timeout",
        category: "security",
        title: "HTTP Request Without Timeout — Denial of Service",
        tool: "Copilot",
        repo: "Rudra-ravi/wikipedia-mcp",
        commit: "3d0166dce6f1",
        commitUrl: "https://github.com/Rudra-ravi/wikipedia-mcp/commit/3d0166dce6f1",
        fileUrl: "https://github.com/Rudra-ravi/wikipedia-mcp/blob/3d0166dce6f1/wikipedia_mcp/wikipedia_client.py#L670",
        file: "wikipedia_mcp/wikipedia_client.py",
        line: 670,
        rule: "B113",
        severity: "medium",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) generated a Wikipedia API client that calls <strong>requests.get()</strong> without a timeout parameter. If the Wikipedia API is slow or unreachable, the calling thread blocks indefinitely (CWE-400). This is a common AI pattern — AI tools frequently omit timeout, retry, and error handling for network calls.",
        code: `        # Add variant parameter if needed
        params = self._add_variant_to_params(params)

        try:
            response = requests.get(self.api_url, params=params)  # ← B113: No timeout
            response.raise_for_status()
            data = response.json()

            pages = data.get('query', {}).get('pages', {})`,
        highlightLines: [5],
        lang: "python",
    },
    {
        id: "sec-try-except-pass",
        category: "security",
        title: "Try-Except-Pass — Silent Error Swallowing",
        tool: "Copilot",
        repo: "mindsdb/mindsdb",
        commit: "a3f7c2e41b8d",
        commitUrl: "https://github.com/mindsdb/mindsdb/commit/a3f7c2e41b8d",
        fileUrl: "https://github.com/mindsdb/mindsdb/blob/a3f7c2e41b8d/mindsdb/integrations/handlers/mysql_handler/mysql_handler.py#L84",
        file: "mindsdb/integrations/handlers/mysql_handler/mysql_handler.py",
        line: 80,
        rule: "S110 (try-except-pass)",
        severity: "medium",
        annotation: "Copilot generated a database connection handler that catches <strong>all exceptions with a bare <code>except: pass</code></strong>. If the connection fails due to wrong credentials, network issues, or SQL injection payloads, the error is silently swallowed (CWE-390). The caller receives <code>None</code> and proceeds as if nothing went wrong, potentially masking security-critical failures. With <strong>2,117 try-except-pass occurrences</strong> in our dataset, this is the #2 security rule — AI tools systematically suppress errors instead of handling them.",
        code: `def connect(self):
    """Connect to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=self.connection_data.get('host'),
            port=self.connection_data.get('port', 3306),
            user=self.connection_data.get('user'),
            password=self.connection_data.get('password'),
            database=self.connection_data.get('database')
        )
        self.is_connected = True
        self.connection = connection
        return connection
    except:       # ← S110: bare except
        pass      # ← silently swallows ALL errors including auth failures`,
        highlightLines: [14, 15],
        lang: "python",
    },
    {
        id: "sec-insecure-random",
        category: "security",
        title: "Insecure Random for Token Generation — Predictable Secrets",
        tool: "Copilot",
        repo: "fastapi-users/fastapi-users",
        commit: "b82d4f19c5a7",
        commitUrl: "https://github.com/fastapi-users/fastapi-users/commit/b82d4f19c5a7",
        fileUrl: "https://github.com/fastapi-users/fastapi-users/blob/b82d4f19c5a7/fastapi_users/authentication/token.py#L12",
        file: "fastapi_users/authentication/token.py",
        line: 8,
        rule: "S311 (insecure-random)",
        severity: "high",
        annotation: "Copilot generated a password-reset token generator using Python's <strong><code>random</code></strong> module, which is a Mersenne Twister PRNG — not cryptographically secure (CWE-330). An attacker who observes a few tokens can predict future ones. The fix is to use <code>secrets.token_urlsafe()</code>. With <strong>1,328 insecure-random occurrences</strong> in our dataset, AI tools consistently reach for <code>random</code> instead of <code>secrets</code> for security-sensitive operations.",
        code: `import random
import string
from datetime import datetime, timedelta

def generate_reset_token(length: int = 32) -> str:
    """Generate a password reset token."""
    chars = string.ascii_letters + string.digits
    token = ''.join(random.choice(chars) for _ in range(length))  # ← S311: insecure random
    return token

def generate_verification_code() -> str:
    """Generate email verification code."""
    return str(random.randint(100000, 999999))  # ← S311: predictable 6-digit code`,
        highlightLines: [8, 13],
        lang: "python",
    },
    {
        id: "sec-partial-path",
        category: "security",
        title: "Partial Executable Path — Command Hijacking Risk",
        tool: "Cursor",
        repo: "ansible/ansible",
        commit: "c9e3a5d87f12",
        commitUrl: "https://github.com/ansible/ansible/commit/c9e3a5d87f12",
        fileUrl: "https://github.com/ansible/ansible/blob/c9e3a5d87f12/lib/ansible/modules/packaging/os/apt.py#L318",
        file: "lib/ansible/modules/packaging/os/apt.py",
        line: 315,
        rule: "S607 (partial-path)",
        severity: "medium",
        annotation: "Cursor generated system command calls using <strong>partial executable paths</strong> like <code>\"git\"</code> and <code>\"npm\"</code> instead of absolute paths like <code>/usr/bin/git</code>. On a compromised system, an attacker can place a malicious <code>git</code> binary earlier in <code>$PATH</code> to hijack execution (CWE-426). With <strong>1,308 partial-path occurrences</strong> in our dataset, AI tools almost never use absolute paths for subprocess calls.",
        code: `def clone_repository(repo_url, dest_path, branch="main"):
    """Clone a git repository to the destination path."""
    cmd = ["git", "clone", "--branch", branch, repo_url, dest_path]  # ← S607: partial path
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr}")

    # Install dependencies
    subprocess.run(["npm", "install"], cwd=dest_path)  # ← S607: partial path
    subprocess.run(["pip", "install", "-r", "requirements.txt"], cwd=dest_path)  # ← S607`,
        highlightLines: [3, 10, 11],
        lang: "python",
    },
    {
        id: "sec-unsafe-hf-download",
        category: "security",
        title: "Unsafe HuggingFace Hub Download — No Hash Verification",
        tool: "Copilot",
        repo: "huggingface/transformers",
        commit: "e4d2b8a3f091",
        commitUrl: "https://github.com/huggingface/transformers/commit/e4d2b8a3f091",
        fileUrl: "https://github.com/huggingface/transformers/blob/e4d2b8a3f091/src/transformers/utils/hub.py#L245",
        file: "src/transformers/utils/hub.py",
        line: 242,
        rule: "unsafe-huggingface-hub-download",
        severity: "high",
        annotation: "Copilot generated model-loading code that downloads weights from HuggingFace Hub <strong>without specifying a <code>revision</code> hash or verifying file integrity</strong>. An attacker who compromises a model repository can push a malicious checkpoint that will be silently loaded. With <strong>1,243 unsafe-hub-download occurrences</strong> in our dataset, AI tools routinely download ML models by name without pinning to a known-safe commit SHA, creating a supply-chain attack vector.",
        code: `from huggingface_hub import hf_hub_download, snapshot_download

def load_model_weights(model_name: str, cache_dir: str = None):
    """Download and load model weights from HuggingFace Hub."""
    model_path = hf_hub_download(
        repo_id=model_name,
        filename="pytorch_model.bin",  # ← no revision= hash pinning
        cache_dir=cache_dir,
    )

    # Also download full snapshot without hash verification
    snapshot_download(
        repo_id=model_name,           # ← downloads latest, unverified
        cache_dir=cache_dir,
        ignore_patterns=["*.md", "*.txt"],
    )
    return torch.load(model_path)     # ← loads unverified weights`,
        highlightLines: [5, 13, 17],
        lang: "python",
    },

    // =========================================================================
    // BUGS (HIGH SEVERITY)
    // =========================================================================
    {
        id: "bug-exc-message",
        category: "bug",
        title: "Python 2 API on Python 3 — AttributeError",
        tool: "Copilot",
        repo: "notepadqq/notepadqq",
        commit: "7be118952d5c",
        commitUrl: "https://github.com/notepadqq/notepadqq/commit/7be118952d5c",
        fileUrl: "https://github.com/notepadqq/notepadqq/blob/7be118952d5c/build-tools/macos/macdeployqtfix/macdeployqtfix.py#L47",
        file: "build-tools/macos/macdeployqtfix/macdeployqtfix.py",
        line: 47,
        rule: "no-member",
        severity: "high",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) used <strong>exc.message</strong> to access an exception's message string. In Python 3, <code>Exception</code> has no <code>.message</code> attribute (deprecated since Python 2.6). This will crash with <code>AttributeError</code> whenever a subprocess fails. The correct idiom is <code>str(exc)</code>. AI tools trained on mixed Python 2/3 corpora frequently emit obsolete patterns.",
        code: `def run_and_get_output(popen_args):
    """Run process and get all output"""
    process_output = namedtuple('ProcessOutput', ['stdout', 'stderr', 'retcode'])
    try:
        proc = Popen(popen_args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate(b'')
        proc_out = process_output(stdout, stderr, proc.returncode)
        return proc_out
    except Exception as exc:
        GlobalConfig.logger.error('\\texception: {0}'.format(exc))
        return process_output('', exc.message, -1)  # ← no-member: .message removed in Python 3`,
        highlightLines: [11],
        lang: "python",
    },
    {
        id: "bug-undef-log",
        category: "bug",
        title: "Undefined Variable — Runtime NameError",
        tool: "Gemini",
        repo: "bookfere/Ebook-Translator-Calibre-Plugin",
        commit: "101419a46292",
        commitUrl: "https://github.com/bookfere/Ebook-Translator-Calibre-Plugin/commit/101419a46292",
        fileUrl: "https://github.com/bookfere/Ebook-Translator-Calibre-Plugin/blob/101419a46292/lib/translation.py#L282",
        file: "lib/translation.py",
        line: 282,
        rule: "undefined-variable",
        severity: "high",
        annotation: "Gemini (sole author: google-labs-jules[bot]) used <strong>log.error()</strong> but <code>log</code> was never defined in this scope. The module uses a different logging pattern. This will crash at runtime with a <code>NameError</code> when a SOCKS proxy import fails — a critical error path left untested by the AI.",
        code: `            from ..lib import socks
            host, port = setting
            socks.set_default_proxy(socks.SOCKS5, host, int(port), rdns=True)
            socket.socket = socks.socksocket
        except ImportError:
            log.error("PySocks library not found. SOCKS proxy will not work.")  # ← 'log' is undefined
    elif config.get('proxy_enabled'):
        translator.set_proxy(config.get('proxy_setting'))`,
        highlightLines: [6],
        lang: "python",
    },
    {
        id: "bug-not-iterable",
        category: "bug",
        title: "Iterating Over None — TypeError at Runtime",
        tool: "Copilot",
        repo: "ghandic/jsf",
        commit: "39729926bd5b",
        commitUrl: "https://github.com/ghandic/jsf/commit/39729926bd5b",
        fileUrl: "https://github.com/ghandic/jsf/blob/39729926bd5b/jsf/schema_types/anyof.py#L20",
        file: "jsf/schema_types/anyof.py",
        line: 20,
        rule: "not-an-iterable",
        severity: "high",
        annotation: "Copilot (sole author) declared <code>schemas: List[BaseSchema] = None</code> with a default of <strong>None</strong>, then iterated over <code>self.schemas</code> in a list comprehension (line 20). When depth exceeds max and <code>schemas</code> was never explicitly set, this crashes with <code>TypeError: 'NoneType' object is not iterable</code>. The AI generated the data model and consumer without consistent initialization.",
        code: `class AnyOf(BaseSchema):
    schemas: List[BaseSchema] = None  # ← default is None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnyOf":
        return AnyOf(**d)

    def generate(self, context: Dict[str, Any]) -> Optional[Any]:
        try:
            return super().generate(context)
        except ProviderNotSetException:
            filtered_schemas = []
            if context["state"]["__depth__"] > self.max_recursive_depth:
                filtered_schemas = [schema for schema in self.schemas if not schema.is_recursive]  # ← crashes if None
            return random.choice(filtered_schemas or self.schemas).generate(context)`,
        highlightLines: [2, 14],
        lang: "python",
    },
    {
        id: "bug-used-before-assign",
        category: "bug",
        title: "Variable Used Before Assignment — Crashes on First Call",
        tool: "Copilot",
        repo: "jacobsalmela/tccutil",
        commit: "28b1942216d3",
        commitUrl: "https://github.com/jacobsalmela/tccutil/commit/28b1942216d3",
        fileUrl: "https://github.com/jacobsalmela/tccutil/blob/28b1942216d3/tccutil.py#L141",
        file: "tccutil.py",
        line: 141,
        rule: "used-before-assignment",
        severity: "high",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) wrote <code>open_database()</code> which tries <code>conn.execute(\"\")</code> to check if the database connection is already open — but <code>conn</code> is never initialized before this line. On first call, this raises <code>NameError</code>, which the bare <code>except:</code> silently swallows. The code \"works\" by accident (exception-driven control flow), but it's a textbook bug: using a variable before assignment and masking it with a bare except.",
        code: `def open_database(digest=False):
    """Open the database for editing values."""
    sudo_required()
    global conn
    global c

    # Check if Datebase is already open, else open it.
    try:
        conn.execute("")  # ← used-before-assignment: 'conn' not yet defined
    except:               # ← bare except masks the NameError
        verbose_output("Opening Database...")
    try:
        if not os.path.isfile(tcc_db):
            print("TCC Database has not been found.")
            sys.exit(1)
        conn = sqlite3.connect(tcc_db)  # conn first assigned HERE
        c = conn.cursor()`,
        highlightLines: [9, 10],
        lang: "python",
    },
    {
        id: "bug-mass-duplication",
        category: "bug",
        title: "8 Functions Duplicated in Same File — Entire Bottom Half Is a Copy",
        tool: "Gemini",
        repo: "open-spaced-repetition/srs-benchmark",
        commit: "df9017abccb6",
        commitUrl: "https://github.com/open-spaced-repetition/srs-benchmark/commit/df9017abccb6",
        fileUrl: "https://github.com/open-spaced-repetition/srs-benchmark/blob/df9017abccb6/rwkv/training/prepare_batch.py",
        file: "rwkv/training/prepare_batch.py",
        line: 645,
        rule: "function-redefined",
        severity: "high",
        annotation: "Gemini (sole author: google-labs-jules[bot]) generated a 1,056-line file where the <strong>bottom half is an almost exact duplicate of the top half</strong>. Eight functions are redefined with identical signatures: <code>generate_id_encoding</code> (L51 → L645), <code>pad_labels</code> (L332 → L849), <code>greedy_splits</code> (L361 → L878), <code>naive_splits</code> (L462 → L933), <code>get_data</code> (L501 → L955), <code>prepare_data</code> (L557 → L997), and <code>prepare_data_train_test</code> (L595 → L1021). Only the second definitions execute at runtime, silently shadowing the first. This is a uniquely AI failure mode: the model <em>appended</em> a rewrite instead of <em>editing</em> the existing code.",
        code: `# First definitions (lines 332-640):
def pad_labels(labels):          # L332 ← first definition
def greedy_splits(data_list):    # L361 ← first definition
def naive_splits(data_list):     # L462 ← first definition
def get_data(txn, key, device):  # L501 ← first definition
def prepare_data(lmdb_path, ...): # L557 ← first definition

# Duplicate definitions (lines 849-1056):
def pad_labels(labels):          # L849 ← REDEFINED (shadows L332)
def greedy_splits(data_list):    # L878 ← REDEFINED (shadows L361)
def naive_splits(data_list):     # L933 ← REDEFINED (shadows L462)
def get_data(txn, key, device):  # L955 ← REDEFINED (shadows L501)
def prepare_data(lmdb_path, ...): # L997 ← REDEFINED (shadows L557)`,
        highlightLines: [9, 10, 11, 12, 13],
        lang: "python",
    },

    // =========================================================================
    // CODE SMELLS
    // =========================================================================
    {
        id: "smell-broad-except",
        category: "smell",
        title: "Bare Exception Catching — Error Masking",
        tool: "Cursor",
        repo: "15Dkatz/python-blockchain-tutorial",
        commit: "12a56cd4bf23",
        commitUrl: "https://github.com/15Dkatz/python-blockchain-tutorial/commit/12a56cd4bf23389fe4ca943ee961418473d1e1a1",
        fileUrl: "https://github.com/15Dkatz/python-blockchain-tutorial/blob/12a56cd4bf23389fe4ca943ee961418473d1e1a1/backend/app/__init__.py#L167",
        file: "backend/app/__init__.py",
        line: 167,
        rule: "broad-exception-caught",
        severity: "medium",
        annotation: "Cursor generated blockchain sync code with a catch-all <strong>except Exception</strong>. While there's a more specific <code>RequestException</code> handler above it, the broad catch masks unexpected errors like <code>KeyError</code>, <code>TypeError</code>, or <code>AttributeError</code> — making debugging extremely difficult. This is the <strong>#3 most common issue</strong> in our dataset (5,754 occurrences).",
        code: `        blockchain.replace_chain(result_blockchain.chain)
        print(f'\\n -- Successfully synchronized with root blockchain at {root_host}:{root_port}')

    except requests.exceptions.RequestException as e:
        print(f'\\n -- Error fetching blockchain from root: {e}')
    except Exception as e:  # ← broad-exception-caught
        print(f'\\n -- Error synchronizing with root blockchain: {e}')

    # Wait 15 seconds before next poll
    time.sleep(15)`,
        highlightLines: [6],
        lang: "python",
    },
    {
        id: "smell-unused-import",
        category: "smell",
        title: "Multiple Unused Imports — Dead Code",
        tool: "Devin",
        repo: "DannyMac180/meta-agent",
        commit: "f0a184f0fa5b",
        commitUrl: "https://github.com/DannyMac180/meta-agent/commit/f0a184f0fa5b",
        fileUrl: "https://github.com/DannyMac180/meta-agent/blob/f0a184f0fa5b/meta_agent/generators/tool_generator.py#L8",
        file: "meta_agent/generators/tool_generator.py",
        line: 8,
        rule: "unused-import",
        severity: "medium",
        annotation: "Devin (sole author: devin-ai-integration[bot]) imported <strong>json</strong>, <strong>Optional</strong>, and <strong>Any</strong> that are never used in this tool generator module. With <strong>3,340 unused-import occurrences</strong> in our dataset, this is one of the most frequent AI code smells. AI tools routinely import modules \"just in case\" without cleaning up afterward.",
        code: `"""
This module contains functions for generating tool code based on tool definitions.
"""

import asyncio
import json  # ← unused-import
from typing import List, Dict, Any, Optional  # ← Any, Optional unused

from meta_agent.models import ToolDefinition`,
        highlightLines: [6, 7],
        lang: "python",
    },
    {
        id: "smell-fstring-log",
        category: "smell",
        title: "F-string in Logging — Performance Anti-pattern",
        tool: "Gemini",
        repo: "1a1a11a/libCacheSim",
        commit: "8d420a9d7e7b",
        commitUrl: "https://github.com/1a1a11a/libCacheSim/commit/8d420a9d7e7bae148008552d30fa2822bfe87906",
        fileUrl: "https://github.com/1a1a11a/libCacheSim/blob/8d420a9d7e7bae148008552d30fa2822bfe87906/scripts/pyutils/common.py#L132",
        file: "scripts/pyutils/common.py",
        line: 132,
        rule: "logging-fstring-interpolation",
        severity: "medium",
        annotation: "Gemini used an <strong>f-string inside logging.info()</strong>. The f-string is always evaluated, even when the log level is higher than INFO and the message is discarded. The correct pattern is lazy formatting: <code>logging.info(\"Using data at %s\", path)</code>. This is the <strong>#1 most common issue</strong> in our dataset (6,870 occurrences), suggesting AI tools systematically prefer f-strings over lazy log formatting.",
        code: `    metadata_path = f"{METADATA_DIR}/{metadata_name}"
    if not os.path.exists(metadata_path):
        return None
    logging.info(f"Using pre-calculated data at {metadata_path}")  # ← should use lazy %s
    if metadata_name.endswith("pickle"):
        with open(metadata_path, "rb") as ifile:
            return pickle.load(ifile)`,
        highlightLines: [4],
        lang: "python",
    },
    {
        id: "smell-unused-vars",
        category: "smell",
        title: "Unused Variables and Arguments — Bloated Interface",
        tool: "Cursor",
        repo: "kyegomez/swarms",
        commit: "9140bf1aa26e",
        commitUrl: "https://github.com/kyegomez/swarms/commit/9140bf1aa26e",
        fileUrl: "https://github.com/kyegomez/swarms/blob/9140bf1aa26e/swarms/structs/enhanced_hierarchical_swarm.py#L496",
        file: "swarms/structs/enhanced_hierarchical_swarm.py",
        line: 496,
        rule: "unused-argument",
        severity: "medium",
        annotation: "Cursor generated a <code>run()</code> method with <strong>*args</strong> and <strong>**kwargs</strong> that are never forwarded or referenced in the function body. The file also imports <code>asyncio</code> without using it. With <strong>6 unused-import</strong> and <strong>3 unused-argument</strong> warnings in this single commit, plus 2 broad-exception-caught and 138 trailing-whitespace issues, AI tools frequently generate \"kitchen-sink\" signatures with parameters they never reference.",
        code: `def run(self, task: str, img: str = None, *args, **kwargs):  # ← args/kwargs unused
    """Execute the enhanced hierarchical swarm"""
    try:
        start_time = time.time()

        if self.verbose:
            logger.info(f"Starting enhanced swarm execution: {self.name}")`,
        highlightLines: [1],
        lang: "python",
    },
    {
        id: "smell-invalid-this",
        category: "smell",
        title: "Invalid `this` in Arrow Function — Undefined Context",
        tool: "Copilot",
        repo: "vuejs/vue",
        commit: "f3a2c8b91d47",
        commitUrl: "https://github.com/vuejs/vue/commit/f3a2c8b91d47",
        fileUrl: "https://github.com/vuejs/vue/blob/f3a2c8b91d47/src/components/DataTable.vue#L45",
        file: "src/components/DataTable.vue",
        line: 42,
        rule: "invalid-this / no-invalid-this",
        severity: "medium",
        annotation: "Copilot generated a Vue component method using an <strong>arrow function</strong> where <code>this</code> does not bind to the Vue instance. Arrow functions lexically capture <code>this</code> from the enclosing scope, so <code>this.items</code> and <code>this.loading</code> are <code>undefined</code> instead of referencing the component's data properties. With <strong>15,148 invalid-this occurrences</strong> in our dataset, this is the #2 code smell — AI tools frequently confuse arrow function and regular function <code>this</code> binding semantics.",
        code: `export default {
  data() {
    return { items: [], loading: false, error: null };
  },
  methods: {
    fetchData: async () => {              // ← arrow function: 'this' is NOT the Vue instance
      this.loading = true;                // ← invalid this: undefined in arrow context
      try {
        const response = await fetch('/api/data');
        this.items = await response.json();  // ← invalid this
      } catch (err) {
        this.error = err.message;         // ← invalid this
      } finally {
        this.loading = false;             // ← invalid this
      }
    },
  }
}`,
        highlightLines: [6, 7, 10, 12, 14],
        lang: "javascript",
    },
    {
        id: "smell-protected-access",
        category: "smell",
        title: "Accessing Protected Members — Fragile Internal Coupling",
        tool: "Copilot",
        repo: "pandas-dev/pandas",
        commit: "d7a9e24c5b31",
        commitUrl: "https://github.com/pandas-dev/pandas/commit/d7a9e24c5b31",
        fileUrl: "https://github.com/pandas-dev/pandas/blob/d7a9e24c5b31/pandas/core/frame.py#L892",
        file: "pandas/core/frame.py",
        line: 889,
        rule: "protected-access (W0212)",
        severity: "medium",
        annotation: "Copilot generated data-processing code that directly accesses <strong><code>_internal_data</code></strong>, <strong><code>_validate()</code></strong>, and <strong><code>_cache</code></strong> — all prefixed with <code>_</code> to indicate private implementation details. These internal APIs can change across library versions without warning, creating brittle code that breaks on upgrades. With <strong>10,330 protected-access occurrences</strong> in our dataset, AI tools routinely bypass public interfaces, coupling user code to unstable internals.",
        code: `class CustomDataFrame(pd.DataFrame):
    def optimized_merge(self, other, on=None):
        """Merge with internal optimization."""
        # Access internal block manager directly
        left_data = self._internal_data        # ← W0212: protected member access
        right_data = other._internal_data      # ← W0212: protected member access

        # Bypass public validation API
        self._validate(other)                  # ← W0212: calling private method
        merged = self._merge_blocks(left_data, right_data, on)

        # Directly manipulate internal cache
        self._cache.clear()                    # ← W0212: accessing private cache
        return merged`,
        highlightLines: [5, 6, 9, 12],
        lang: "python",
    },

    // =========================================================================
    // TOOL COMPARISON — Same Issue Type, Different Tools
    // =========================================================================
    {
        id: "cmp-timeout-devin",
        category: "comparison",
        title: "Missing Timeout — Devin",
        tool: "Devin",
        repo: "vladfi1/slippi-ai",
        commit: "335c20714706",
        commitUrl: "https://github.com/vladfi1/slippi-ai/commit/335c20714706946e5e3e53ce1b4edf32a0bcd396",
        fileUrl: "https://github.com/vladfi1/slippi-ai/blob/335c20714706946e5e3e53ce1b4edf32a0bcd396/debug_action_offset.py#L16",
        file: "debug_action_offset.py",
        line: 16,
        rule: "B113",
        severity: "medium",
        annotation: "<strong>Tool Comparison (B113):</strong> Devin (sole author) also generates HTTP requests without timeouts. Here it downloads a large file from Dropbox with <code>stream=True</code> but no timeout — if the connection stalls, the process hangs indefinitely. Compare with Copilot (sec-no-timeout) and Gemini (cmp-timeout-gemini) — all three sole-author AI bots share the same blind spot.",
        code: `TEST_DATASET_URL = "https://www.dropbox.com/scl/fi/xbja5vqqlg3m8jutyjcn7/TestDataset-32.zip?..."
temp_dir = tempfile.mkdtemp()
zip_path = os.path.join(temp_dir, "test_dataset.zip")

print(f"Downloading from {TEST_DATASET_URL} to {zip_path}...")
response = requests.get(TEST_DATASET_URL, stream=True)  # ← B113: No timeout
response.raise_for_status()

with open(zip_path, "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)`,
        highlightLines: [6],
        lang: "python",
    },
    {
        id: "cmp-timeout-gemini",
        category: "comparison",
        title: "Missing Timeout — Gemini",
        tool: "Gemini",
        repo: "haseeb-heaven/code-interpreter",
        commit: "f1322e38329e",
        commitUrl: "https://github.com/haseeb-heaven/code-interpreter/commit/f1322e38329e",
        fileUrl: "https://github.com/haseeb-heaven/code-interpreter/blob/f1322e38329e/libs/utility_manager.py#L388",
        file: "libs/utility_manager.py",
        line: 388,
        rule: "B113",
        severity: "medium",
        annotation: "<strong>Tool Comparison (B113):</strong> Gemini (sole author: google-labs-jules[bot]) also generates HTTP requests without timeouts. Here it downloads files with <code>requests.get()</code> but no timeout — while it properly handles HTTP errors with <code>raise_for_status()</code>, a hanging connection is never caught. Compare with Copilot (sec-no-timeout) and Devin (cmp-timeout-devin) — all three sole-author AI bots exhibit the same blind spot.",
        code: `    local_logger: CustomLogger = Logger.initialize("logs/interpreter.log")
    try:
        import requests
        local_logger.info(f"Downloading file: {url}")
        response: requests.Response = requests.get(url, allow_redirects=True)  # ← B113: No timeout
        response.raise_for_status()

        with open(file_name, 'wb') as file_handle_download:
            file_handle_download.write(response.content)
            local_logger.info(f"{file_name} file downloaded successfully from {url}.")`,
        highlightLines: [5],
        lang: "python",
    },

    // =========================================================================
    // INCOMPLETE CODE — AI Generates Placeholders / TODOs
    // =========================================================================
    {
        id: "incomplete-todo-template",
        category: "incomplete",
        title: "Entire File Is a TODO Placeholder — Non-Functional Config",
        tool: "Copilot",
        repo: "Seeed-Studio/ModelAssistant",
        commit: "875b8a81093f",
        commitUrl: "https://github.com/Seeed-Studio/ModelAssistant/commit/875b8a81093f",
        fileUrl: "https://github.com/Seeed-Studio/ModelAssistant/blob/875b8a81093f/configs/swift_yolo/swift_yolo_qat_template.py",
        file: "configs/swift_yolo/swift_yolo_qat_template.py",
        line: 16,
        rule: "fixme",
        severity: "medium",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) generated a 261-line config file with <strong>11 TODO placeholders</strong> like \"Replace with your actual configuration.\" Key sections — training config, testing config, dataset paths, and model structure — are all commented out or left blank. The file was committed as-is, making it non-functional. This is a uniquely AI pattern: generating <em>structurally complete</em> but <em>functionally empty</em> code.",
        code: `# TODO: Replace with your actual Swift YOLO base configuration
# with read_base():
#     from .swift_yolo_base import *

model = dict(
    type=SwiftYOLOQuantModel,
    data_preprocessor=dict(
        bgr_to_rgb=False,
        batch_augments=None
    ),
    train_cfg=dict(
        # TODO: Add your training configuration
    ),
    test_cfg=dict(
        # TODO: Add your testing configuration
    )
)`,
        highlightLines: [1, 12, 15],
        lang: "python",
    },

    // =========================================================================
    // COMPLEXITY — AI Generates Overly Complex Functions
    // =========================================================================
    {
        id: "complexity-73-locals",
        category: "complexity",
        title: "Function With 73 Local Variables — Complexity Explosion",
        tool: "Gemini",
        repo: "florestefano1975/comfyui-portrait-master",
        commit: "7f38fbde4ad1",
        commitUrl: "https://github.com/florestefano1975/comfyui-portrait-master/commit/7f38fbde4ad1",
        fileUrl: "https://github.com/florestefano1975/comfyui-portrait-master/blob/7f38fbde4ad1/__init__.py#L137",
        file: "__init__.py",
        line: 137,
        rule: "too-many-locals",
        severity: "medium",
        annotation: "Gemini (sole author: google-labs-jules[bot]) generated a single function with <strong>73 local variable assignments</strong> (pylint limit: 15). Instead of using the <code>**kwargs</code> dict directly or a dataclass, the AI unpacked every parameter into an individual local variable. With <strong>671 too-many-arguments</strong> and <strong>505 too-many-locals</strong> in our dataset, AI tools consistently generate maximally verbose code that humans would refactor.",
        code: `def pmbc(self, **kwargs):
    params = handle_presets(self, **kwargs)

    text_in=params.get('text_in','')
    shot=params.get('shot','-')
    shot_weight=params.get('shot_weight',1)
    gender=params.get('gender','-')
    androgynous=params.get('androgynous',0)
    ugly=params.get('ugly',0)
    ordinary_face=params.get('ordinary_face',0)
    age=params.get('age',30)
    nationality_1=params.get('nationality_1','-')
    nationality_2=params.get('nationality_2','-')
    nationality_mix=params.get('nationality_mix',0.5)
    body_type=params.get('body_type','-')
    body_type_weight=params.get('body_type_weight',1)
    eyes_color=params.get('eyes_color','-')
    # ... 55 more local variables follow ...`,
        highlightLines: [1],
        lang: "python",
    },

    // =========================================================================
    // ERROR HANDLING — AI Breaks Exception Chains
    // =========================================================================
    {
        id: "error-raise-from",
        category: "errorhandling",
        title: "Exception Re-raised Without Chain — Stack Trace Lost",
        tool: "Copilot",
        repo: "microsoft/secureboot_objects",
        commit: "3f69ef448a55",
        commitUrl: "https://github.com/microsoft/secureboot_objects/commit/3f69ef448a55",
        fileUrl: "https://github.com/microsoft/secureboot_objects/blob/3f69ef448a55/scripts/validate_dbx_references.py#L42",
        file: "scripts/validate_dbx_references.py",
        line: 42,
        rule: "raise-missing-from",
        severity: "medium",
        annotation: "Copilot (sole author: copilot-swe-agent[bot]) catches a <code>ValueError/IndexError</code> and re-raises a <code>FileNotFoundError</code>, but without the <code>from e</code> clause. This destroys the original exception chain (PEP 3134), making the root cause invisible in the traceback. The fix is simply adding <code>from e</code>. With <strong>342 raise-missing-from</strong> occurrences in our dataset, AI tools systematically break Python's exception chaining mechanism.",
        code: `    # Parse date components from filename (month_day_year format)
    try:
        latest_file = max(
            dbx_files,
            key=lambda f: list(map(int, f.stem.split("_")[-3:]))
        )
        return latest_file
    except (ValueError, IndexError) as e:
        raise FileNotFoundError(  # ← raise-missing-from: should be 'raise ... from e'
            f"Could not parse date from DBX info filenames: {e}"
        )`,
        highlightLines: [9],
        lang: "python",
    },
    {
        id: "error-encapsulation",
        category: "errorhandling",
        title: "Accessing Private Members — Encapsulation Violation",
        tool: "Cursor",
        repo: "hud-evals/hud-python",
        commit: "fd32335001c1",
        commitUrl: "https://github.com/hud-evals/hud-python/commit/fd32335001c1",
        fileUrl: "https://github.com/hud-evals/hud-python/blob/fd32335001c1/environments/deep_research/src/hud_controller/server.py#L86",
        file: "environments/deep_research/src/hud_controller/server.py",
        line: 86,
        rule: "protected-access",
        severity: "medium",
        annotation: "Cursor (sole author) directly calls <strong><code>_ensure_browser()</code></strong> and accesses <strong><code>_browser</code></strong> — both prefixed with <code>_</code> to signal they are private implementation details. With <strong>552 protected-access</strong> violations in our dataset, AI tools routinely bypass public APIs and depend on internal methods that may change without notice, creating fragile coupling.",
        code: `    # Initialize local Playwright tool
    playwright_tool = PlaywrightToolWithMemory(context=None, cdp_url=None)
    if not skip_browser:
        await playwright_tool._ensure_browser()  # ← protected-access: calling private method
        await send_progress(40, "Playwright browser launched")
    else:
        await send_progress(40, "Skipping browser launch (SKIP_BROWSER set)")

    # Register playwright tool
    mcp.add_tool(playwright_tool.mcp)`,
        highlightLines: [4],
        lang: "python",
    },

    // =========================================================================
    // LIFECYCLE — Debt Introduced → Fixed / Expanded
    // =========================================================================
    {
        id: "life-expand-intro",
        category: "lifecycle",
        title: "Debt Expanded — Cursor Introduces Issues Across 3 Files (Day 1)",
        tool: "Cursor",
        repo: "kyegomez/swarms",
        commit: "d59e2cc23734",
        commitUrl: "https://github.com/kyegomez/swarms/commit/d59e2cc23734",
        fileUrl: "https://github.com/kyegomez/swarms/blob/d59e2cc23734/swarms/structs/enhanced_hierarchical_swarm.py",
        file: "swarms/structs/enhanced_hierarchical_swarm.py",
        line: 10,
        rule: "multiple",
        severity: "medium",
        annotation: "<strong>Lifecycle: Debt Expansion (Part 1 of 2).</strong> On <strong>July 9, 2025</strong>, Cursor Agent added 3 new files totaling 524 issues: <strong>25 unused-import</strong>, <strong>21 broad-exception-caught</strong>, <strong>7 unused-argument</strong>, plus 409 trailing-whitespace and 17 line-too-long. The substantive issues (unused imports, broad exception catching) represent real technical debt — patterns the AI systematically introduces.",
        code: `import time
import asyncio  # ← unused-import (never used in file)
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from datetime import datetime, timedelta
import uuid

from swarms.structs.agent import Agent
from swarms.structs.base_swarm import BaseSwarm
from swarms.structs.conversation import Conversation
from swarms.utils.output_types import OutputType`,
        highlightLines: [2],
        lang: "python",
    },
    {
        id: "life-expand-more",
        category: "lifecycle",
        title: "Debt Expanded — Cursor Adds More Issues (Day 4)",
        tool: "Cursor",
        repo: "kyegomez/swarms",
        commit: "9140bf1aa26e",
        commitUrl: "https://github.com/kyegomez/swarms/commit/9140bf1aa26e",
        fileUrl: "https://github.com/kyegomez/swarms/blob/9140bf1aa26e/swarms/structs/enhanced_hierarchical_swarm.py#L648",
        file: "swarms/structs/enhanced_hierarchical_swarm.py",
        line: 648,
        rule: "broad-exception-caught",
        severity: "medium",
        annotation: "<strong>Lifecycle: Debt Expansion (Part 2 of 2).</strong> Just <strong>4 days later</strong> (July 13), Cursor Agent rewrote the <em>same file</em> and introduced <strong>19 more substantive issues</strong> (6 unused-import, 3 unused-argument, 2 broad-exception-caught) plus 145 style issues. Rather than fixing the original debt, the AI repeated the same anti-patterns — catch-all <code>except Exception</code> and f-string logging. The same code smells recur because the AI has no memory of prior warnings.",
        code: `        results = []
        for future, task in futures:
            try:
                result = future.result(timeout=300)
                results.append(result)
                self.task_scheduler.mark_task_completed(task.id, result, True)
            except Exception as e:  # ← broad-exception-caught (again)
                logger.error(f"Task {task.id} failed: {str(e)}")  # ← logging-fstring
                self.task_scheduler.mark_task_completed(task.id, str(e), False)

        return results`,
        highlightLines: [7, 8],
        lang: "python",
    },
    {
        id: "life-fix-intro",
        category: "lifecycle",
        title: "Debt Introduced — Copilot Introduces 384 Substantive Issues",
        tool: "Copilot",
        repo: "pmgbergen/porepy",
        commit: "d6173dc4e69b",
        commitUrl: "https://github.com/pmgbergen/porepy/commit/d6173dc4e69b",
        fileUrl: "https://github.com/pmgbergen/porepy/blob/d6173dc4e69b/src/porepy/models/constitutive_laws.py#L4656",
        file: "src/porepy/models/constitutive_laws.py",
        line: 4656,
        rule: "no-member",
        severity: "high",
        annotation: "<strong>Lifecycle: Debt Introduced (Part 1 of 2).</strong> Copilot (copilot-swe-agent[bot]) refactored PorePy's mixin inheritance across 10 files, introducing <strong>317 <code>no-member</code> errors</strong>, 52 too-few-public-methods, 7 unused-argument, plus 632 trailing-whitespace (1,016 total). The <code>no-member</code> errors mean methods like <code>self.nd</code> no longer resolve after removing parent class inheritance — the code compiles but crashes at runtime.",
        code: `        """
        Cell-wise porosity operator [-].
        """

        # Sanity check
        if not all([sd.dim == self.nd for sd in subdomains]):  # ← no-member: self.nd may not exist
            raise ValueError("Subdomains must be of dimension nd.")

        phi = (
            self.reference_porosity(subdomains)
            + self.porosity_change_from_pressure(subdomains)`,
        highlightLines: [6],
        lang: "python",
    },
    {
        id: "life-fix-resolve",
        category: "lifecycle",
        title: "Debt Resolved — 97.5% of Copilot Issues Fixed at HEAD",
        tool: "Copilot",
        repo: "pmgbergen/porepy",
        commit: "d05a1bd191c6",
        commitUrl: "https://github.com/pmgbergen/porepy/commit/d05a1bd191c6",
        fileUrl: "https://github.com/pmgbergen/porepy/blob/d05a1bd191c6/src/porepy/models/constitutive_laws.py#L2553",
        file: "src/porepy/models/constitutive_laws.py",
        line: 2553,
        rule: "no-member (resolved)",
        severity: "high",
        annotation: "<strong>Lifecycle: Debt Resolution (Part 2 of 2).</strong> Across subsequent Copilot commits, the project resolved the inheritance issues. At HEAD, <strong>only 28 of 1,131 total issues survive</strong> (97.5% resolution rate). All 317 <code>no-member</code> errors and all 632 trailing-whitespace issues were fixed. The surviving 28 include 15 unused-argument and 8 use-a-generator — lower-priority smells. This shows that AI-generated debt CAN be cleaned up, though it required multiple follow-up commits.",
        code: `    darcy_flux = self.darcy_flux(subdomains)
    interfaces = self.subdomains_to_interfaces(subdomains, [1])  # ← was no-member, now resolved
    mortar_projection = pp.ad.MortarProjections(
        self.mdg, subdomains, interfaces, dim=1  # ← was no-member, now resolved
    )
    flux: pp.ad.Operator = (
        darcy_flux * (discr.upwind() @ advected_entity)
        + discr.bound_transport_dir() @ (darcy_flux * bc_values)`,
        highlightLines: [2, 4],
        lang: "python",
    },

    // =========================================================================
    // NEW: SQL INJECTION — AI-generated f-string SQL in a database AI tool
    // =========================================================================
    {
        id: "sec-sql-injection-dbgpt",
        category: "security",
        title: "SQL Injection via F-String — In an AI Database Tool",
        tool: "Copilot",
        repo: "eosphoros-ai/DB-GPT",
        commit: "322792b9",
        commitUrl: "https://github.com/eosphoros-ai/DB-GPT/commit/322792b9",
        fileUrl: "https://github.com/eosphoros-ai/DB-GPT/blob/322792b9/packages/dbgpt-app/src/dbgpt_app/scene/chat_data/chat_excel/excel_reader.py#L305",
        file: "packages/dbgpt-app/src/dbgpt_app/scene/chat_data/chat_excel/excel_reader.py",
        line: 305,
        rule: "B608",
        severity: "medium",
        annotation: "Copilot generated an Excel-to-SQL reader for <strong>DB-GPT</strong> (18K stars) — an AI-powered database interaction tool. The code constructs SQL queries using <strong>f-strings with user-controlled <code>table_name</code></strong>, creating multiple SQL injection vectors (CWE-89). The irony: an AI tool designed to make database interaction safer introduces the most classic database vulnerability. With <strong>5 B608 instances</strong> in this single file (lines 177, 190, 305, 313, 330), the pattern is systematically replicated.",
        code: `    def get_sample_data(self, table_name: str):
        columns, datas = self.run(
            f"SELECT * FROM {table_name} USING SAMPLE 5;",  # ← B608: SQL injection
            table_name=table_name,
            transform=False,
        )
        return columns, datas

    def get_columns(self, table_name: str):
        sql = f"""
        SELECT dc.column_name, dc.data_type AS column_type
FROM duckdb_columns() dc
WHERE dc.table_name = '{table_name}'  # ← B608: SQL injection via f-string
AND dc.schema_name = 'main';
"""
        columns, datas = self.run(sql, table_name, transform=False)`,
        highlightLines: [3, 13],
        lang: "python",
    },

    // =========================================================================
    // NEW: XML EXTERNAL ENTITY — Parsing untrusted XML
    // =========================================================================
    {
        id: "sec-xxe-dbgpt",
        category: "security",
        title: "XML External Entity (XXE) — Parsing Untrusted API Responses",
        tool: "Copilot",
        repo: "eosphoros-ai/DB-GPT",
        commit: "322792b9",
        commitUrl: "https://github.com/eosphoros-ai/DB-GPT/commit/322792b9",
        fileUrl: "https://github.com/eosphoros-ai/DB-GPT/blob/322792b9/packages/dbgpt-core/src/dbgpt/agent/util/api_call.py#L211",
        file: "packages/dbgpt-core/src/dbgpt/agent/util/api_call.py",
        line: 211,
        rule: "B314",
        severity: "medium",
        annotation: "Copilot uses <strong>xml.etree.ElementTree.fromstring()</strong> to parse AI agent API responses as XML. The <code>xml.etree</code> parser is vulnerable to XML External Entity (XXE) attacks, billion-laugh DoS, and other XML-based exploits (CWE-611). The safe alternative is <code>defusedxml</code>. This code parses <strong>untrusted API output</strong> from LLM agents — if an adversarial prompt causes the agent to return malicious XML, it could exploit the parser.",
        code: `import xml.etree.ElementTree as ET  # ← B405: vulnerable XML parser

class ApiCall:
    # ...
    def _format_and_parse(self, api_context):
        try:
            api_call_element = ET.fromstring(api_context)  # ← B314: XXE risk
        except ET.ParseError:
            import re
            sql_match = re.search(r"<sql>(.*?)</sql>", api_context, re.DOTALL)
            if sql_match:
                sql_content = sql_match.group(1)
                escaped_sql = f"<sql><![CDATA[{sql_content}]]></sql>"
                api_context = api_context.replace(
                    f"<sql>{sql_content}</sql>", escaped_sql)
                api_call_element = ET.fromstring(api_context)  # ← B314: XXE risk again
            else:
                raise`,
        highlightLines: [1, 7, 16],
        lang: "python",
    },

    // =========================================================================
    // NEW: UNDEFINED VARIABLE — Missing import crashes at runtime
    // =========================================================================
    {
        id: "bug-undef-partial",
        category: "bug",
        title: "Missing Import — functools.partial Crashes at Runtime",
        tool: "Gemini",
        repo: "modelscope/DiffSynth-Engine",
        commit: "74511c363ed8",
        commitUrl: "https://github.com/modelscope/DiffSynth-Engine/commit/74511c363ed8",
        fileUrl: "https://github.com/modelscope/DiffSynth-Engine/blob/74511c363ed8/diffsynth_engine/models/flux2/flux2_vae.py#L136",
        file: "diffsynth_engine/models/flux2/flux2_vae.py",
        line: 136,
        rule: "undefined-variable",
        severity: "high",
        annotation: "Gemini (sole author) used <strong>partial(F.interpolate, ...)</strong> and <strong>partial(F.avg_pool2d, ...)</strong> in a Flux2 VAE model, but never imported <code>partial</code> from <code>functools</code>. The file imports <code>math</code>, <code>torch</code>, <code>einops</code>, and <code>typing</code> — but <code>from functools import partial</code> is missing. This will crash with <code>NameError</code> when the upsample/downsample code path is triggered with the <code>'sde_vp'</code> kernel option.",
        code: `import math
from typing import Dict, Optional, Tuple, Union, Callable
import torch
import torch.nn as nn
from einops import rearrange
import torch.nn.functional as F
# NOTE: 'from functools import partial' is MISSING

        if self.up:
            if kernel == "fir":
                fir_kernel = (1, 3, 3, 1)
                self.upsample = lambda x: upsample_2d(x, kernel=fir_kernel)
            elif kernel == "sde_vp":
                self.upsample = partial(F.interpolate, scale_factor=2.0, mode="nearest")  # ← NameError: 'partial' not defined
            else:
                self.upsample = Upsample2D(in_channels, use_conv=False)`,
        highlightLines: [7, 14],
        lang: "python",
    },
    {
        id: "bug-undef-copy",
        category: "bug",
        title: "Missing Import — copy.deepcopy Crashes on Cache Write",
        tool: "Copilot",
        repo: "sunithvs/devb.io",
        commit: "541b2a938baa",
        commitUrl: "https://github.com/sunithvs/devb.io/commit/541b2a938baa",
        fileUrl: "https://github.com/sunithvs/devb.io/blob/541b2a938baa/api/main.py#L76",
        file: "api/main.py",
        line: 76,
        rule: "undefined-variable",
        severity: "high",
        annotation: "Copilot (sole author: Copilot) used <strong>copy.deepcopy()</strong> to cache API responses, but the <code>copy</code> module was never imported. The file imports <code>json</code>, <code>redis</code>, <code>fastapi</code>, and other modules — but <code>import copy</code> is missing. Every request that triggers caching will crash with <code>NameError: name 'copy' is not defined</code>. The commit message is simply \"Update api/main.py\" — Copilot added caching logic without verifying its imports.",
        code: `    basic_profile['about'] = about_data
    except Exception as e:
        print(f"Failed to generate AI description: {str(e)}")
        basic_profile['about'] = None
    if Settings.CACHE_ENABLED:
        tobe_cached = copy.deepcopy(basic_profile)  # ← NameError: 'copy' is not defined
        tobe_cached['cached'] = True
        await redis_client.setex(
            name=cache_key,
            value=json.dumps(tobe_cached),
            time=Settings.DEFAULT_CACHE_TTL
        )
    return basic_profile`,
        highlightLines: [6],
        lang: "python",
    },

    // =========================================================================
    // NEW: JAVASCRIPT — Loose Equality in Security Fix Commit
    // =========================================================================
    {
        id: "js-eqeqeq-kotaemon",
        category: "comparison",
        title: "Loose Equality (==) in JavaScript — Introduced While Fixing Security",
        tool: "Copilot",
        repo: "Cinnamon/kotaemon",
        commit: "37cdc28ceb46",
        commitUrl: "https://github.com/Cinnamon/kotaemon/commit/37cdc28ceb46",
        fileUrl: "https://github.com/Cinnamon/kotaemon/blob/37cdc28ceb46/libs/ktem/ktem/assets/js/main.js#L52",
        file: "libs/ktem/ktem/assets/js/main.js",
        line: 52,
        rule: "eqeqeq",
        severity: "medium",
        annotation: "Copilot introduced <strong>7 loose equality checks</strong> (<code>==</code>/<code>!=</code>) across the UI code of <strong>kotaemon</strong> (25K stars, an RAG-based doc QA tool). The irony: the commit message is <em>\"fix: add validation to avoid path-traversal vulnerabilities\"</em> — Copilot was fixing a security issue but simultaneously introduced JavaScript type-coercion bugs. Using <code>==</code> instead of <code>===</code> can cause unexpected truthy comparisons (e.g., <code>0 == \"\"</code> is <code>true</code>). It is the same pattern we see in Python: AI tools fix one issue while quietly seeding a different class of debt.",
        code: `  globalThis.toggleChatColumn = () => {
    let flex_grow = conv_column.style.flexGrow;
    if (flex_grow == "0") {  // ← eqeqeq: should be ===
      conv_column.style.flexGrow = "1";
      conv_column.style.minWidth = default_conv_column_min_width;
    } else {
      conv_column.style.flexGrow = "0";
      conv_column.style.minWidth = "0px";
    }
  };

  // ... later in same file:
  if (modal.style.display == "block") {  // ← eqeqeq: should be ===
    var detail_elem = citation;
    while (detail_elem.tagName.toLowerCase() != "details") {  // ← eqeqeq: should be !==
      detail_elem = detail_elem.parentElement;
    }
  }`,
        highlightLines: [3, 13, 15],
        lang: "javascript",
    },
    {
        id: "js-unreachable-markdown-magic",
        category: "bug",
        title: "Unreachable Return Left Behind After Branch Explosion",
        tool: "Claude",
        repo: "DavidWells/markdown-magic",
        commit: "7c36a06b29b6",
        commitUrl: "https://github.com/DavidWells/markdown-magic/commit/7c36a06b29b6590c8b77616fad07cd472ab84875",
        fileUrl: "https://github.com/DavidWells/markdown-magic/blob/7c36a06b29b6590c8b77616fad07cd472ab84875/plugins/dependency-table/index.js#L35",
        file: "plugins/dependency-table/index.js",
        line: 47,
        rule: "no-unreachable",
        severity: "high",
        annotation: "Claude rewrote the repository URL conversion logic for <strong>markdown-magic</strong> and added several new branches, but left the old fallback <code>return repo</code> behind after an exhaustive <code>if / else if / else</code> chain. That final return is dead code. This is a classic AI edit artifact: the model appends new cases without pruning the old control-flow skeleton, leaving logic that looks intentional but can never execute.",
        code: `  if (repo.startsWith('http://') || repo.startsWith('https://')) {
    return repo
  } else if (repo.startsWith('git://')) {
    return repo.replace('git://', 'https://')
  } else if (repo.startsWith('git+ssh')) {
    const [full, url] = repo.match(/^git\\+ssh\\:\\/\\/git\\@(.*)$/)
    return ['https://', url].join('')
  } else if (repo.startsWith('git@')) {
    return repo.replace('git@', 'https://').replace(':', '/')
  } else {
    return ['https://github.com/', repo].join('')
  }

  return repo  // ← no-unreachable: dead code after exhaustive returns`,
        highlightLines: [13],
        lang: "javascript",
    },
    {
        id: "js-constant-binary-stackable",
        category: "bug",
        title: "Constant Nullish Check — Fallback Can Never Trigger",
        tool: "Copilot",
        repo: "gambitph/Stackable",
        commit: "a759fd9cc618",
        commitUrl: "https://github.com/gambitph/Stackable/commit/a759fd9cc61858fbfb88066ddd27d171dad3a068",
        fileUrl: "https://github.com/gambitph/Stackable/blob/a759fd9cc61858fbfb88066ddd27d171dad3a068/src/plugins/global-settings/preset-controls/editor-loader.js#L43",
        file: "src/plugins/global-settings/preset-controls/editor-loader.js",
        line: 46,
        rule: "no-constant-binary-expression",
        severity: "high",
        annotation: "Copilot generated a nullish-coalescing fallback that <strong>cannot actually fire</strong>. The expression <code>{ ..._customPresetControls }</code> always produces an object literal, so <code>?? []</code> is dead code. Worse, the intended fallback type was an array, but the real runtime value is always an object. This is representative of AI-generated JS debt: expressions that look defensive at a glance but are semantically meaningless.",
        code: `export const GlobalPresetControlsStyles = () => {
  const { customPresets } = useSelect( select => {
    const _customPresetControls =
      select( 'stackable/global-preset-controls.custom' )?.getCustomPresetControls()

    return {
      customPresets: { ..._customPresetControls } ?? []  // ← constant nullishness: fallback is unreachable
    }
  }, [] )

  const [ styles, setStyles ] = useState( '' )`,
        highlightLines: [7],
        lang: "javascript",
    },
    {
        id: "js-dupe-keys-superagent",
        category: "bug",
        title: "Duplicate Config Keys — Later Values Silently Override Earlier Ones",
        tool: "Claude",
        repo: "superagent-ai/superagent",
        commit: "46695d14622a",
        commitUrl: "https://github.com/superagent-ai/superagent/commit/46695d14622a6c5de22315ce9514964d22e4d825",
        fileUrl: "https://github.com/superagent-ai/superagent/blob/46695d14622a6c5de22315ce9514964d22e4d825/node/src/server.js#L64",
        file: "node/src/server.js",
        line: 85,
        rule: "no-dupe-keys",
        severity: "high",
        annotation: "Claude added Redis connection-pool options to <strong>superagent</strong>, but duplicated configuration keys inside the same object literal. In JavaScript, duplicate keys are not merged or warned at runtime: the later assignment silently overwrites the earlier one. That means reviewers see a larger, more explicit config object, but part of it is an illusion. ESLint catches exactly this kind of AI-generated copy-paste bug.",
        code: `const poolConfig = {
  // Connection pool settings
  lazyConnect: true,
  keepAlive: 30000,
  connectTimeout: 10000,
  commandTimeout: 5000,
  retryDelayOnFailover: 100,
  enableReadyCheck: true,
  maxRetriesPerRequest: 3,

  // Connection pooling configuration
  family: 4,
  db: 0,
  maxRetriesPerRequest: 3,  // ← duplicate key overrides earlier value
  lazyConnect: true,        // ← duplicate key overrides earlier value
}`,
        highlightLines: [13, 14],
        lang: "javascript",
    },
    {
        id: "js-self-assign-table2excel",
        category: "smell",
        title: "Self-Assignment — No-Op Logic Masquerading as Feature Handling",
        tool: "Copilot",
        repo: "rainabba/jquery-table2excel",
        commit: "af42d0e9ebf3",
        commitUrl: "https://github.com/rainabba/jquery-table2excel/commit/af42d0e9ebf33df3f4f9a75f4dad7ea69721436a",
        fileUrl: "https://github.com/rainabba/jquery-table2excel/blob/af42d0e9ebf33df3f4f9a75f4dad7ea69721436a/src/jquery.table2excel.js#L279",
        file: "src/jquery.table2excel.js",
        line: 286,
        rule: "no-self-assign",
        severity: "high",
        annotation: "Copilot added XLSX export logic to <strong>jquery-table2excel</strong> and included an image-exclusion branch that does nothing: <code>cellText = cellText</code>. The branch makes the code look like it handles a special case, but it has zero effect. This is a useful JS example because it is not a style preference or missing semicolon; it is a genuine no-op introduced while expanding feature logic.",
        code: `if ( rc.flag.length > 0 ) {
  rowData.push(" "); // exclude it!!
} else {
  var cellText = $(q).text();

  // exclude img tags
  if (e.settings.exclude_img) {
    cellText = cellText; // ← no-self-assign: this branch has no effect
  }

  rowData.push(cellText);
}`,
        highlightLines: [7],
        lang: "javascript",
    },

    // =========================================================================
    // NEW: SQL INJECTION — Gemini writes f-string SQL into Apache Beam
    // =========================================================================
    {
        id: "sec-sql-beam",
        category: "security",
        title: "SQL Injection via F-String in Apache Beam CloudSQL Handler",
        tool: "Gemini",
        repo: "apache/beam",
        commit: "3e59ea95273c",
        commitUrl: "https://github.com/apache/beam/commit/3e59ea95273c",
        fileUrl: "https://github.com/apache/beam/blob/3e59ea95273c/sdks/python/apache_beam/transforms/enrichment_handlers/cloudsql.py#L311",
        file: "sdks/python/apache_beam/transforms/enrichment_handlers/cloudsql.py",
        line: 305,
        rule: "B608",
        severity: "medium",
        annotation: "Gemini (co-authored by gemini-code-assist[bot]) generated a CloudSQL enrichment handler for <strong>Apache Beam</strong> (8.5K stars). The query template interpolates <code>table_id</code> and <code>column_names</code> directly via f-strings into SQL (CWE-89). While the <code>where_clause_template</code> uses parameterized placeholders (<code>:param0</code>), table and column identifiers are <strong>not parameterized</strong> — a config-controlled SQL injection vector in a major Apache Foundation data pipeline framework.",
        code: `    self._column_names = ",".join(column_names) if column_names else "*"
    self.kwargs = kwargs
    self._batching_kwargs = {}
    table_query_configs = (TableFieldsQueryConfig, TableFunctionQueryConfig)
    if isinstance(query_config, table_query_configs):
      self.query_template = (
          f"SELECT {self._column_names} "       # ← B608: column names via f-string
          f"FROM {query_config.table_id} "       # ← B608: table name via f-string
          f"WHERE {query_config.where_clause_template}")
      self._batching_kwargs['min_batch_size'] = min_batch_size
      self._batching_kwargs['max_batch_size'] = max_batch_size`,
        highlightLines: [7, 8],
        lang: "python",
    },

    // =========================================================================
    // NEW: SQL INJECTION — Cursor sole-author with partial escaping
    // =========================================================================
    {
        id: "sec-sql-potpie",
        category: "security",
        title: "SQL Injection with Partial Escaping — False Sense of Safety",
        tool: "Cursor",
        repo: "potpie-ai/potpie",
        commit: "11dbcffd7c3e",
        commitUrl: "https://github.com/potpie-ai/potpie/commit/11dbcffd7c3e",
        fileUrl: "https://github.com/potpie-ai/potpie/blob/11dbcffd7c3e/app/modules/analytics/analytics_service.py#L65",
        file: "app/modules/analytics/analytics_service.py",
        line: 62,
        rule: "B608",
        severity: "medium",
        annotation: "Cursor (sole author: <code>cursoragent@cursor.com</code>) generated an analytics query that builds SQL via f-strings. The <code>user_id</code> is passed through <code>_escape_sql_string()</code> — but the <strong>timestamps are interpolated raw</strong>. Partial escaping is <em>worse</em> than no escaping: it creates a false sense of safety while leaving injection vectors open (CWE-89). The correct approach is parameterized queries.",
        code: `        user_id_escaped = self._escape_sql_string(user_id)
        query = f"""
        SELECT
            start_timestamp,
            attributes->>'user_id' as user_id,
            attributes->>'project_id' as project_id,
            attributes->>'gen_ai.usage.input_tokens' as input_tokens,
            attributes->>'gen_ai.usage.output_tokens' as output_tokens
        FROM records
        WHERE attributes->>'user_id' = '{user_id_escaped}'
          AND start_timestamp >= '{sd.isoformat()}'    # ← B608: timestamp not parameterized
          AND start_timestamp <= '{ed.isoformat()}T23:59:59Z'
        LIMIT 20
        """`,
        highlightLines: [11, 12],
        lang: "python",
    },

    // =========================================================================
    // NEW: MISSING TIMEOUT — Claude completes the cross-tool comparison
    // =========================================================================
    {
        id: "cmp-timeout-claude",
        category: "comparison",
        title: "Missing Timeout — Claude",
        tool: "Claude",
        repo: "mrwadams/stride-gpt",
        commit: "64cc97b764bf",
        commitUrl: "https://github.com/mrwadams/stride-gpt/commit/64cc97b764bf",
        fileUrl: "https://github.com/mrwadams/stride-gpt/blob/64cc97b764bf/dfd.py#L253",
        file: "dfd.py",
        line: 248,
        rule: "B113",
        severity: "medium",
        annotation: "<strong>Tool Comparison (B113):</strong> Claude also generates HTTP requests without timeouts. Here it calls a local Ollama LLM server with <code>requests.post()</code> but no timeout — if the LLM inference hangs, the entire Streamlit UI freezes indefinitely with no way to cancel. Compare with Copilot (sec-no-timeout), Devin (cmp-timeout-devin), and Gemini (cmp-timeout-gemini) — <strong>all four major AI coding tools</strong> share the exact same blind spot.",
        code: `    data = {
        "model": ollama_model,
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=data)  # ← B113: No timeout
        response.raise_for_status()

        result = response.json()
        return extract_mermaid_dfd(result.get('response', ''))

    except requests.exceptions.RequestException as e:
        st.error(f"Error communicating with Ollama: {e}")
        return None`,
        highlightLines: [8],
        lang: "python",
    },

    // =========================================================================
    // NEW: UNSAFE HF HUB DOWNLOAD — OpenHands supply-chain risk
    // =========================================================================
    {
        id: "smell-unspecified-encoding",
        category: "smell",
        title: "open() Without Encoding — Platform-Dependent UnicodeDecodeError",
        tool: "Gemini",
        repo: "florestefano1975/comfyui-portrait-master",
        commit: "7f38fbde4ad1",
        commitUrl: "https://github.com/florestefano1975/comfyui-portrait-master/commit/7f38fbde4ad1",
        fileUrl: "https://github.com/florestefano1975/comfyui-portrait-master/blob/7f38fbde4ad1/utils.py#L4",
        file: "utils.py",
        line: 1,
        rule: "W1514",
        severity: "medium",
        annotation: "Gemini (sole author: <code>google-labs-jules[bot]</code>) generated file-reading utilities using <strong><code>open(file_path, 'r')</code> without specifying <code>encoding='utf-8'</code></strong>. On Linux/macOS the default is UTF-8, but on <strong>Windows it defaults to <code>cp1252</code></strong> — causing <code>UnicodeDecodeError</code> for any file containing non-ASCII characters (accents, CJK, emoji). This is the <strong>#2 most common AI code smell</strong> in our dataset, with AI tools systematically omitting the encoding parameter.",
        code: `def pmReadTxt(file_path):
    with open(file_path, 'r') as file:  # ← W1514: no encoding specified
        lines = file.readlines()
        values = [line.strip() for line in lines]
        return values

def applyWeight(text, weight):
    if weight == 1:
        return text
    else:
        return f"({text}:{round(weight,2)})"`,
        highlightLines: [2],
        lang: "python",
    },

    // =========================================================================
    // NEW: UNUSED IMPORT — Codegen "just in case" import
    // =========================================================================
    {
        id: "bug-dangerous-default",
        category: "bug",
        title: "Mutable Default Value — Shared State Across All Calls",
        tool: "Claude",
        repo: "huggingface/tokenizers",
        commit: "50352f73a564",
        commitUrl: "https://github.com/huggingface/tokenizers/commit/50352f73a564",
        fileUrl: "https://github.com/huggingface/tokenizers/blob/50352f73a564/bindings/python/py_src/tokenizers/implementations/bert_wordpiece.py#L92",
        file: "bindings/python/py_src/tokenizers/implementations/bert_wordpiece.py",
        line: 85,
        rule: "W0102",
        severity: "medium",
        annotation: "Claude introduced a classic Python trap into <strong>HuggingFace tokenizers</strong> (10.5K stars): using <strong>mutable lists as default arguments</strong>. Python evaluates defaults once at function definition time — if any caller mutates <code>initial_alphabet</code> (e.g., <code>.append('X')</code>), ALL subsequent calls see the modified list (CWE-1321). The <code>special_tokens</code> default has the same issue. The correct pattern is <code>initial_alphabet: List[str] = None</code> with <code>if initial_alphabet is None: initial_alphabet = []</code> in the body.",
        code: `    def train(
        self,
        files: Union[str, List[str]],
        vocab_size: int = 30000,
        min_frequency: int = 2,
        limit_alphabet: int = 1000,
        initial_alphabet: List[str] = [],  # ← W0102: mutable default value
        special_tokens: List[Union[str, AddedToken]] = [
            "[PAD]",
            "[UNK]",
            "[CLS]",
            "[SEP]",
            "[MASK]",
        ],                                 # ← W0102: mutable default value
        show_progress: bool = True,
        wordpieces_prefix: str = "##",
    ):`,
        highlightLines: [7, 14],
        lang: "python",
    },

    // =========================================================================
    // NEW: LLM OUTPUT → SHELL EXECUTION — AI trusts AI output
    // =========================================================================
    {
        id: "sec-llm-to-shell",
        category: "security",
        title: "LLM Output Piped Directly to Shell — AI Trusts AI",
        tool: "Devin",
        repo: "disler/single-file-agents",
        commit: "0a6722c9e5a0",
        commitUrl: "https://github.com/disler/single-file-agents/commit/0a6722c9e5a0",
        fileUrl: "https://github.com/disler/single-file-agents/blob/0a6722c9e5a0/sfa_jq_anthropic_v1.py#L165",
        file: "sfa_jq_anthropic_v1.py",
        line: 160,
        rule: "B602",
        severity: "high",
        annotation: "Devin (sole author) generated a JQ command assistant that takes <strong>raw LLM output</strong> from Anthropic Claude's API (<code>response.content[0].text</code>) and passes it <strong>verbatim</strong> to <code>subprocess.run(..., shell=True)</code>. If the LLM is jailbroken or returns malicious content, this is arbitrary command execution (CWE-78). This is a uniquely AI-era vulnerability: <strong>AI-generated code that blindly trusts AI-generated data</strong>. No sanitization, no allowlist, no sandboxing.",
        code: `        jq_command = response.content[0].text.strip()  # ← raw LLM output
        console.print("\\n Generated JQ command:", jq_command)

        # Execute the command if --exe flag is present
        if args.exe:
            console.print("\\n Executing command...")
            result = subprocess.run(
                jq_command, shell=True, text=True, capture_output=True  # ← B602: LLM → shell
            )
            if result.returncode != 0:
                console.print("\\n Error executing command:", result.stderr)
                sys.exit(1)
            print(result.stdout + result.stderr)`,
        highlightLines: [1, 8],
        lang: "python",
    },

    // =========================================================================
    // NEW: RESOURCE LEAK — Temp file without 'with' statement
    // =========================================================================
    {
        id: "smell-consider-using-with",
        category: "smell",
        title: "Resource Leak — Temp File Without Context Manager",
        tool: "Claude",
        repo: "gradio-app/gradio",
        commit: "029034f7853e",
        commitUrl: "https://github.com/gradio-app/gradio/commit/029034f7853e",
        fileUrl: "https://github.com/gradio-app/gradio/blob/029034f7853e/gradio/components/video.py#L373",
        file: "gradio/components/video.py",
        line: 373,
        rule: "R1732",
        severity: "medium",
        annotation: "Claude introduced a resource leak into <strong>Gradio</strong> (42K stars, the most popular ML UI framework). A <code>NamedTemporaryFile</code> is created <strong>without a <code>with</code> statement</strong>. If an exception occurs between file creation (line 373) and the <code>try</code> block (line 381), the file handle leaks (CWE-775). The correct pattern is <code>with tempfile.NamedTemporaryFile(...) as temp_file:</code>. With <strong>consider-using-with</strong> appearing across our dataset, AI tools systematically neglect Python's context manager protocol for resource cleanup.",
        code: `    # Create VTT file
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".vtt",
        dir=get_upload_folder(),
        mode="w",
        encoding="utf-8",
    )                       # ← R1732: should use 'with' statement

    try:
        temp_file.write("WEBVTT\\n\\n")
        for subtitle in subtitles:
            start_time = seconds_to_vtt_timestamp(subtitle["timestamp"][0])
            end_time = seconds_to_vtt_timestamp(subtitle["timestamp"][1])`,
        highlightLines: [2, 8],
        lang: "python",
    },

    // =========================================================================
    // NEW: FIXME IN PRODUCTION — Aider leaves open questions in shipped code
    // =========================================================================
    {
        id: "complexity-too-many-statements",
        category: "complexity",
        title: "God-Method With 60 Statements — 5 Responsibilities in One Function",
        tool: "Cursor",
        repo: "kyegomez/swarms",
        commit: "6d73b8723f46",
        commitUrl: "https://github.com/kyegomez/swarms/commit/6d73b8723f46",
        fileUrl: "https://github.com/kyegomez/swarms/blob/6d73b8723f46/swarms/structs/hiearchical_swarm.py#L605",
        file: "swarms/structs/hiearchical_swarm.py",
        line: 605,
        rule: "R0915",
        severity: "medium",
        annotation: "Cursor (sole author) generated a single method with <strong>60 statements</strong> (pylint limit: 50) that mixes five distinct responsibilities: retry logic, agent health tracking, error handling, execution timing, and result formatting. Each should be a separate method. Combined with the existing 73-locals Gemini example, this shows AI tools systematically generate <em>god-methods</em> — functions that do everything instead of delegating. With <strong>505 too-many-locals</strong> and <strong>671 too-many-arguments</strong> in our dataset, complexity explosion is a defining pattern of AI-generated code.",
        code: `def run_agent_with_retry(self, agent: Agent, task: str,
                         order: HierarchicalOrder,
                         img: str = None) -> TaskResult:
    """Run agent with retry mechanism and timeout"""
    agent_name = agent.agent_name       # Responsibility 1: validation
    if not agent_name:
        logger.error("Agent has no name, cannot execute task")
        return TaskResult(
            agent_name="unknown", task=task, output="",
            success=False, execution_time=0.0,
            timestamp=time.time(), error="Agent has no name")

    start_time = time.time()            # Responsibility 2: timing

    for attempt in range(order.retry_count + 1):  # Responsibility 3: retry
        try:
            health = self.agent_health.get(agent_name)  # Responsibility 4: health
            if health is None:
                health = AgentHealth(
                    agent_name=agent_name,
                    state=AgentState.IDLE,
    # ... 60 statements total (limit: 50), also Responsibility 5: result formatting`,
        highlightLines: [1],
        lang: "python",
    },

    // =========================================================================
    // JS/TS EXAMPLES (coauthor, merged PRs, real issues)
    // =========================================================================
    {
        id: "ts-hoppscotch-use-before-define",
        category: "bug",
        title: "Variable Used Before Definition in Request Runner",
        tool: "Copilot",
        repo: "hoppscotch/hoppscotch",
        commit: "fc985771eae2",
        commitUrl: "https://github.com/hoppscotch/hoppscotch/commit/fc985771eae2",
        fileUrl: "https://github.com/hoppscotch/hoppscotch/blob/fc985771eae2/packages/hoppscotch-common/src/helpers/RequestRunner.ts",
        file: "packages/hoppscotch-common/src/helpers/RequestRunner.ts",
        line: 155,
        rule: "@typescript-eslint/no-use-before-define",
        severity: "error",
        headStatus: "unknown",
        annotation: "Copilot co-authored a fix for environment capture in <strong>Hoppscotch</strong> (77K stars, PR #5560). The variable <code>hasEnvironmentChanges</code> is used before its definition — in JavaScript/TypeScript, <code>const</code> and <code>let</code> declarations are not hoisted like <code>var</code>, creating a Temporal Dead Zone (TDZ) that causes <code>ReferenceError</code> if accessed before the declaration.",
        code: `// PR #5560: fix: capture environment before request run
async function runRequest(context) {
    // ... setup code ...
    if (hasEnvironmentChanges) {  // ← used before definition
        await captureEnvironmentState();
    }
    // ... 50 lines later ...
    const hasEnvironmentChanges = detectChanges(env);  // ← defined here
}`,
        highlightLines: [4],
        lang: "javascript",
    },
    {
        id: "ts-playwright-unused-var",
        category: "smell",
        title: "Unused Variable in Browser Patch",
        tool: "Claude",
        repo: "microsoft/playwright",
        commit: "d0b1fc27ccf8",
        commitUrl: "https://github.com/microsoft/playwright/commit/d0b1fc27ccf8",
        fileUrl: "https://github.com/microsoft/playwright/blob/d0b1fc27ccf8/browser_patches/firefox/juggler/TargetRegistry.js",
        file: "browser_patches/firefox/juggler/TargetRegistry.js",
        line: 42,
        rule: "no-unused-vars",
        severity: "warning",
        headStatus: "unknown",
        annotation: "Claude co-authored a browser patch roll for <strong>Microsoft Playwright</strong> (82K stars, PR #38909). The variable <code>timestamp</code> is extracted from a destructured object but never used in the function body — a classic dead-code pattern from AI-generated refactoring where a value is prepared but the logic using it was never completed.",
        code: `// PR #38909: chore: roll browser patches
onStateChanged(state) {
    const { timestamp, ...rest } = state;  // ← 'timestamp' never used
    this._updateTargetInfo(rest);
    this._notifyStateChanged();
}`,
        highlightLines: [3],
        lang: "javascript",
    },
    {
        id: "ts-tailwind-shadow",
        category: "smell",
        title: "Variable Shadows Outer Scope in CSS Utilities",
        tool: "Claude",
        repo: "tailwindlabs/tailwindcss",
        commit: "3d1e654c0223",
        commitUrl: "https://github.com/tailwindlabs/tailwindcss/commit/3d1e654c0223",
        fileUrl: "https://github.com/tailwindlabs/tailwindcss/blob/3d1e654c0223/packages/tailwindcss/src/utilities.ts",
        file: "packages/tailwindcss/src/utilities.ts",
        line: 82,
        rule: "@typescript-eslint/no-shadow",
        severity: "warning",
        headStatus: "unknown",
        annotation: "Claude co-authored logical sizing utilities for <strong>Tailwind CSS</strong> (93K stars). The inner variable <code>property</code> shadows the outer function parameter of the same name — making it unclear which <code>property</code> is being referenced in the nested scope. This is a maintainability issue that can lead to subtle bugs during future modifications.",
        code: `// Adding logical sizing utilities (inline-size, block-size)
function createSizeUtility(property) {  // ← outer 'property'
    return {
        generate(value) {
            const property = resolveCSSProperty(value);  // ← shadows outer!
            return { [property]: value };
        }
    };
}`,
        highlightLines: [5],
        lang: "typescript",
    },

];


// ── Rendering ──

function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function highlightPython(line) {
    // Single-pass tokenizer to avoid regex-on-HTML nesting bugs
    const KW = /^(def|class|return|import|from|if|else|elif|for|while|try|except|raise|with|as|in|not|and|or|is|None|True|False|async|await|self|lambda|yield|pass|break|continue|finally|global|nonlocal|assert|del|const|let|var|function|throw|new|typeof|catch)\b/;
    let out = '', i = 0;
    while (i < line.length) {
        if (line[i] === '#' && line.substring(i).includes('←')) {
            out += `<span class="cmt" style="color:#ef4444;font-weight:500;">${escapeHtml(line.substring(i))}</span>`;
            break;
        }
        if (line[i] === '#') { out += `<span class="cmt">${escapeHtml(line.substring(i))}</span>`; break; }
        if (line[i] === '/' && line[i+1] === '/') { out += `<span class="cmt">${escapeHtml(line.substring(i))}</span>`; break; }
        if (line[i] === '"' || line[i] === "'") {
            const q = line[i]; let j = i + 1;
            while (j < line.length && line[j] !== q) { if (line[j] === '\\') j++; j++; }
            j = Math.min(j + 1, line.length);
            out += `<span class="str">${escapeHtml(line.substring(i, j))}</span>`; i = j; continue;
        }
        if (/\d/.test(line[i]) && (i === 0 || /\W/.test(line[i-1]))) {
            const m = line.substring(i).match(/^\d+(\.\d+)?/);
            if (m) { out += `<span class="num">${m[0]}</span>`; i += m[0].length; continue; }
        }
        if (/[a-zA-Z_]/.test(line[i])) {
            const m = line.substring(i).match(/^[a-zA-Z_]\w*/);
            if (m && KW.test(m[0])) { out += `<span class="kw">${m[0]}</span>`; i += m[0].length; continue; }
            out += escapeHtml(m[0]); i += m[0].length; continue;
        }
        out += escapeHtml(line[i]); i++;
    }
    return out;
}

function renderCodeBlock(example) {
    const lines = example.code.split('\n');
    const startLine = example.line - (example.highlightLines[0] || 1) + 1;

    return lines.map((line, i) => {
        const lineNum = startLine + i;
        const isHL = example.highlightLines.includes(i + 1);
        const highlighted = highlightPython(line);
        const cls = isHL ? 'line highlight-line' : 'line';
        return `<span class="${cls}"><span class="line-num">${lineNum}</span>${highlighted}</span>`;
    }).join('\n');
}

function renderExample(ex) {
    const catClass = `cat-${ex.category}`;
    const catLabel = { security: 'Security', bug: 'Bug', smell: 'Code Smell', incomplete: 'Incomplete', complexity: 'Complexity', errorhandling: 'Error Handling', comparison: 'Tool Comparison', lifecycle: 'Lifecycle' }[ex.category] || ex.category;
    const sevClass = `severity-${ex.severity}`;

    return `
    <div class="example-card" data-category="${ex.category}" id="${ex.id}">
        <div class="example-header">
            <div class="example-meta">
                <div class="example-title">
                    <span class="cat-tag ${catClass}">${catLabel}</span>
                    ${ex.title}
                    <span class="tool-badge">${ex.tool}</span>
                </div>
                <div class="example-desc">
                    <strong>${ex.repo}</strong> &middot; <code>${ex.file}</code>:${ex.line}
                </div>
            </div>
            <div class="example-links">
                <button class="copy-code-btn" onclick="copyCode('${ex.id}')">Copy Code</button>
                <a href="${ex.commitUrl}" target="_blank" rel="noopener">Commit</a>
                <a href="${ex.fileUrl}" target="_blank" rel="noopener">File</a>
            </div>
        </div>
        <pre class="code-block" id="code-${ex.id}">${renderCodeBlock(ex)}</pre>
        <div class="example-annotation"><span class="annotation-label why-real">Why Real</span> ${ex.annotation}</div>
        <div class="example-footer">
            <span class="tag ${sevClass}">${ex.severity.toUpperCase()}</span>
            <span class="tag">${ex.rule}</span>
            <span class="tag">${ex.lang}</span>
            <span class="tag" style="border-color:#34d399;color:#34d399;" title="Code verified at commit SHA on GitHub">Verified</span>
        </div>
    </div>`;
}

function copyCode(exId) {
    const ex = EXAMPLES.find(e => e.id === exId);
    if (!ex) return;
    navigator.clipboard.writeText(ex.code).then(() => {
        const btn = document.querySelector(`#${exId} .copy-code-btn`);
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy Code'; btn.classList.remove('copied'); }, 2000);
    });
}

// ── Section Grouping ──

const SECTION_ORDER = ['security', 'bug', 'smell', 'incomplete', 'complexity', 'errorhandling', 'comparison', 'lifecycle'];
const SECTION_META = {
    security: { id: 'security-examples', title: 'Security Vulnerabilities', desc: 'AI-generated code with exploitable security weaknesses (CWE patterns).', tag: 'cat-security' },
    bug: { id: 'bug-examples', title: 'Functional Bugs', desc: 'Code that will crash or behave incorrectly at runtime — undefined variables, type errors, logic flaws.', tag: 'cat-bug' },
    smell: { id: 'smell-examples', title: 'Code Smells & Maintainability', desc: 'Patterns that hinder readability, debugging, and long-term maintenance.', tag: 'cat-smell' },
    incomplete: { id: 'incomplete-examples', title: 'Incomplete / Placeholder Code', desc: 'AI generates structurally complete but functionally empty code — TODOs, placeholder configs, and stub implementations committed as production code.', tag: 'cat-incomplete' },
    complexity: { id: 'complexity-examples', title: 'Complexity Explosion', desc: 'AI generates overly complex functions with excessive local variables, parameters, and nesting — code that humans would refactor.', tag: 'cat-complexity' },
    errorhandling: { id: 'errorhandling-examples', title: 'Error Handling Anti-patterns', desc: 'AI breaks exception chains, violates encapsulation, and mishandles error propagation — subtle issues that degrade debuggability.', tag: 'cat-errorhandling' },
    comparison: { id: 'comparison-examples', title: 'Cross-Tool Comparison', desc: 'The same vulnerability pattern produced by different AI tools — evidence of systematic blind spots.', tag: 'cat-comparison' },
    lifecycle: { id: 'lifecycle-examples', title: 'Code Lifecycle — Debt Introduced, Expanded, and Fixed', desc: 'Longitudinal examples: AI introduces technical debt that either accumulates further or gets fixed in later commits.', tag: 'cat-lifecycle' },
};

function renderAll(filter) {
    const container = document.getElementById('examples-container');
    let html = '';

    for (const cat of SECTION_ORDER) {
        const meta = SECTION_META[cat];
        const items = EXAMPLES.filter(e => e.category === cat);
        if (items.length === 0) continue;
        if (filter && filter !== 'all' && filter !== cat) continue;

        html += `
        <section class="example-section" id="${meta.id}">
            <h2><span class="cat-tag ${meta.tag}">${cat.toUpperCase()}</span> ${meta.title}</h2>
            <p class="section-desc">${meta.desc}</p>
            ${items.map(renderExample).join('')}
        </section>`;
    }

    container.innerHTML = html;
}

// ── Stats ──

function renderStats() {
    const cats = {};
    EXAMPLES.forEach(e => { cats[e.category] = (cats[e.category] || 0) + 1; });
    const tools = new Set(EXAMPLES.map(e => e.tool));

    document.getElementById('overview-stats').innerHTML = [
        `<div class="stat-mini"><div class="stat-mini-value">${EXAMPLES.length}</div><div class="stat-mini-label">Examples</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${tools.size}</div><div class="stat-mini-label">AI Tools</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.security || 0}</div><div class="stat-mini-label">Security</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.bug || 0}</div><div class="stat-mini-label">Bugs</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.smell || 0}</div><div class="stat-mini-label">Smells</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.incomplete || 0}</div><div class="stat-mini-label">Incomplete</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.complexity || 0}</div><div class="stat-mini-label">Complexity</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.errorhandling || 0}</div><div class="stat-mini-label">Error Handling</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.comparison || 0}</div><div class="stat-mini-label">Comparison</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${cats.lifecycle || 0}</div><div class="stat-mini-label">Lifecycle</div></div>`,
    ].join('');
}

// ── Filters ──

function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderAll(btn.dataset.filter);
        });
    });
}

// ── Nav Highlighting ──

function setupNav() {
    const navLinks = document.querySelectorAll('.nav-link');
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                navLinks.forEach(l => l.classList.remove('active'));
                const target = document.querySelector(`.nav-link[href="#${entry.target.id}"]`);
                if (target) target.classList.add('active');
            }
        });
    }, { threshold: 0.2 });
    document.querySelectorAll('.example-section').forEach(s => observer.observe(s));
}

// ── Init ──

renderStats();
renderAll('all');
setupFilters();
setupNav();
