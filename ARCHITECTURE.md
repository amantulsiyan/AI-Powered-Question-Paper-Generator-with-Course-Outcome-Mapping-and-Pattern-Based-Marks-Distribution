# System Architecture - AI MCQ Generator v2.0

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                    (Netlify/Vercel - Static)                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  index.html  │  │ result.html  │  │   CSS/JS     │        │
│  │  (Upload)    │  │  (Display)   │  │  (Styling)   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│                    (Render - Free Tier)                         │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                      app.py (Routes)                      │ │
│  │  • POST /generate    • GET /download/{file}              │ │
│  │  • GET /health       • GET /stats                        │ │
│  │  • POST /admin/clear-cache                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌──────────────┬────────────┴────────────┬──────────────┐    │
│  │              │                          │              │    │
│  ▼              ▼                          ▼              ▼    │
│ ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  │
│ │ Rate   │  │ Input  │  │ Cache  │  │ Logger │  │ Config │  │
│ │Limiter │  │Validator│  │Manager │  │        │  │Manager │  │
│ └────────┘  └────────┘  └────────┘  └────────┘  └────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  mcq_core.py (Core Logic)                 │ │
│  │                                                           │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │ │
│  │  │   Text      │  │    MCQ      │  │    CO       │     │ │
│  │  │ Extraction  │  │ Generation  │  │  Mapping    │     │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │ │
│  │                                                           │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │ │
│  │  │   Bloom     │  │    File     │  │   Retry     │     │ │
│  │  │  Detection  │  │   Savers    │  │   Logic     │     │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (Parallel Async Calls)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         GROQ API                                │
│                  (Llama 3.3 70B Versatile)                      │
│                                                                 │
│  Rate Limit: 30 requests/minute                                │
│  Timeout: 120 seconds                                          │
│  Retry: 3 attempts with exponential backoff                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Request Flow (Detailed)

### 1. User Submits Request

```
User (Browser)
    │
    │ 1. Upload file/URL + COs + question count
    ▼
Frontend (index.html)
    │
    │ 2. FormData with validation
    ▼
Backend (/generate endpoint)
```

### 2. Backend Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Request Validation & Rate Limiting                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Rate Limiter ──► Check IP ──► Allow/Deny                      │
│       │                              │                          │
│       │ (5/min, 100/hour)           │                          │
│       ▼                              ▼                          │
│  Pydantic Validator ──► Sanitize ──► Validate                  │
│       │                              │                          │
│       │ • Question count (1-100)    │                          │
│       │ • CO count (1-20)           │                          │
│       │ • File size (<10MB)         │                          │
│       │ • Topic name (alphanumeric) │                          │
│       ▼                              ▼                          │
│  ✅ Valid Request                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Text Extraction                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  File Upload? ──Yes──► Stream to Disk (8KB chunks)             │
│       │                        │                                │
│       No                       ▼                                │
│       │                Extract Text (PDF/DOCX/TXT)             │
│       │                        │                                │
│       ▼                        │                                │
│  URL Input ──► Async Fetch ───┘                                │
│                        │                                        │
│                        ▼                                        │
│                  Clean & Normalize                              │
│                        │                                        │
│                        ▼                                        │
│                  ✅ Extracted Text                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Cache Check                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Generate Cache Key (SHA256)                                   │
│       │                                                         │
│       │ Key = hash(text + COs + count)                         │
│       ▼                                                         │
│  Check Cache ──► Hit? ──Yes──► Return Cached Result ──► DONE   │
│       │                                                         │
│       No (Miss)                                                 │
│       │                                                         │
│       ▼                                                         │
│  Continue to Generation                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Parallel MCQ Generation (ASYNC)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Calculate Questions per CO                                     │
│       │                                                         │
│       │ base = total // num_cos                                │
│       │ extra = total % num_cos                                │
│       │ buffer = +20% per CO                                   │
│       ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Parallel API Calls (asyncio.gather)              │  │
│  │                                                          │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐       │  │
│  │  │  CO1   │  │  CO2   │  │  CO3   │  │  CO4   │  ...  │  │
│  │  │ +20%   │  │ +20%   │  │ +20%   │  │ +20%   │       │  │
│  │  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘       │  │
│  │      │           │           │           │             │  │
│  │      └───────────┴───────────┴───────────┘             │  │
│  │                      │                                  │  │
│  │                      ▼                                  │  │
│  │              All execute in parallel                    │  │
│  │              (not sequential!)                          │  │
│  │                      │                                  │  │
│  │                      ▼                                  │  │
│  │         ┌────────────────────────────┐                 │  │
│  │         │   Retry Logic (Tenacity)   │                 │  │
│  │         │   • 3 attempts              │                 │  │
│  │         │   • Exponential backoff     │                 │  │
│  │         │   • 2-10 second delays      │                 │  │
│  │         └────────────────────────────┘                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│                    ✅ Raw MCQ Text                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Parsing & Validation                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Split by "## MCQ" delimiter                                   │
│       │                                                         │
│       ▼                                                         │
│  For each block:                                               │
│       │                                                         │
│       ├──► Extract Question                                    │
│       ├──► Extract Options (A, B, C, D)                        │
│       ├──► Extract Correct Answer                              │
│       │                                                         │
│       ├──► Validate: 4 options? ──No──► Skip (Log Warning)    │
│       │                    │                                    │
│       │                   Yes                                   │
│       │                    │                                    │
│       ├──► Validate: Valid answer? ──No──► Skip (Log Warning) │
│       │                    │                                    │
│       │                   Yes                                   │
│       │                    │                                    │
│       └──► ✅ Valid MCQ                                         │
│                                                                 │
│  Result: List of valid MCQs                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: CO Mapping (Optimized Jaccard)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Precompute CO Keywords (once)                                 │
│       │                                                         │
│       │ CO1_keywords = set(tokenize(CO1))                      │
│       │ CO2_keywords = set(tokenize(CO2))                      │
│       │ ...                                                     │
│       ▼                                                         │
│  For each MCQ:                                                 │
│       │                                                         │
│       ├──► Tokenize question                                   │
│       ├──► Compare with all CO keyword sets                    │
│       ├──► Calculate Jaccard similarity                        │
│       ├──► Select best match                                   │
│       └──► Assign CO + similarity score                        │
│                                                                 │
│  10x faster than naive approach!                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Bloom Level Detection                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  For each MCQ:                                                 │
│       │                                                         │
│       ├──► Extract first word                                  │
│       ├──► Check keyword lists                                 │
│       ├──► Apply heuristics                                    │
│       └──► Assign Bloom level                                  │
│                                                                 │
│  Levels: Remember, Understand, Apply, Analyze, Evaluate, Create│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Retry Logic (if needed)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Count valid MCQs                                              │
│       │                                                         │
│       ├──► Enough? ──Yes──► Continue                           │
│       │              │                                          │
│       │             No                                          │
│       │              │                                          │
│       └──► Generate more (up to 3 cycles)                      │
│                      │                                          │
│                      ▼                                          │
│              Trim to exact count                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 9: Cache & Save                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Store in Cache (60-min TTL)                                   │
│       │                                                         │
│       ▼                                                         │
│  Generate Timestamp (IST)                                      │
│       │                                                         │
│       │ Format: YYYYMMDD_HHMMSS                                │
│       ▼                                                         │
│  Save Files (parallel):                                        │
│       │                                                         │
│       ├──► TXT  (plain text with answers at end)               │
│       ├──► PDF  (formatted with FPDF2)                         │
│       ├──► DOCX (formatted with python-docx)                   │
│       └──► JSON (structured data)                              │
│                                                                 │
│  Filenames: {topic}_{timestamp}.{ext}                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 10: Response                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Return JSON:                                                  │
│       │                                                         │
│       ├──► mcqs_raw (text)                                     │
│       ├──► mapped_mcqs (array)                                 │
│       ├──► txt_filename                                        │
│       ├──► pdf_filename                                        │
│       ├──► docx_filename                                       │
│       └──► json_filename                                       │
│                                                                 │
│  Frontend displays results + download links                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Interactions

### Rate Limiter
```
┌──────────────┐
│ Rate Limiter │
├──────────────┤
│ • Per-IP     │
│ • 5/min      │──► Token Bucket Algorithm
│ • 100/hour   │
│ • In-memory  │──► Deque with timestamps
└──────────────┘
```

### Cache Manager
```
┌──────────────┐
│    Cache     │
├──────────────┤
│ • SHA256 key │──► hash(content + COs + count)
│ • 60-min TTL │
│ • In-memory  │──► Dict with timestamps
│ • Auto-clean │──► Expire on access
└──────────────┘
```

### Logger
```
┌──────────────┐
│    Logger    │
├──────────────┤
│ • Structured │──► Timestamp + Level + Message
│ • Console    │
│ • File (opt) │──► logs/app.log
│ • Levels     │──► INFO, WARNING, ERROR
└──────────────┘
```

### Config Manager
```
┌──────────────┐
│    Config    │
├──────────────┤
│ • Pydantic   │──► Type-safe settings
│ • .env file  │
│ • Defaults   │──► Sensible defaults
│ • Validation │──► On startup
└──────────────┘
```

---

## Performance Characteristics

### Before Optimization
```
Sequential API Calls:
CO1 ──► 8s ──► CO2 ──► 8s ──► CO3 ──► 8s ──► CO4 ──► 8s ──► CO5 ──► 8s
Total: 40 seconds
```

### After Optimization
```
Parallel API Calls:
CO1 ──► 8s ──┐
CO2 ──► 8s ──┤
CO3 ──► 8s ──┼──► max(8s) = 8 seconds
CO4 ──► 8s ──┤
CO5 ──► 8s ──┘
Total: 8 seconds (5x faster!)
```

---

## Memory Usage

### Before (Synchronous)
```
File Upload: 50MB
├─ Buffer in memory: 50MB
├─ Text extraction: 10MB
├─ API payload: 10MB
└─ Total: 70MB (risk of OOM)
```

### After (Streaming)
```
File Upload: 50MB
├─ Stream to disk: 8KB chunks
├─ Text extraction: 10MB
├─ API payload: 10MB
└─ Total: 20MB (safe)
```

---

## Error Handling Flow

```
Request
   │
   ├──► Rate Limit? ──Yes──► 429 Error
   │         │
   │        No
   │         │
   ├──► Valid Input? ──No──► 400 Error
   │         │
   │        Yes
   │         │
   ├──► File Too Large? ──Yes──► 400 Error
   │         │
   │        No
   │         │
   ├──► API Call Fails? ──Yes──► Retry (3x)
   │         │                      │
   │        No                      │
   │         │                      ├──► Still Fails? ──► 500 Error
   │         │                      │
   │         │                     Success
   │         │                      │
   ├──► Parse Fails? ──Yes──► Log Warning, Continue
   │         │
   │        No
   │         │
   └──► ✅ Success ──► 200 Response
```

---

## Scalability Limits

### Current (Free Tier)
```
Groq API: 30 req/min
Backend: 512MB RAM, shared CPU
Frontend: 100GB bandwidth/month

Max Throughput:
├─ Without cache: 300 req/hour
├─ With 50% cache: 600 req/hour
└─ With parallel: 5x faster response
```

### Bottlenecks at 10x Load
```
1. Groq API rate limit (30/min)
   └─ Solution: Paid tier or user API keys

2. Render CPU throttling
   └─ Solution: Upgrade to paid tier

3. Memory constraints (512MB)
   └─ Solution: Already optimized with streaming
```

---

## Security Layers

```
┌─────────────────────────────────────────┐
│ Layer 1: Rate Limiting                  │
│ • Per-IP tracking                       │
│ • 5/min, 100/hour                       │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Layer 2: Input Validation               │
│ • Pydantic models                       │
│ • Type checking                         │
│ • Range validation                      │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Layer 3: Sanitization                   │
│ • Topic name cleaning                   │
│ • CO text truncation                    │
│ • URL validation                        │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Layer 4: File Validation                │
│ • Extension check                       │
│ • Size limit (10MB)                     │
│ • Secure filename                       │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Layer 5: Error Handling                 │
│ • Try-catch blocks                      │
│ • Graceful degradation                  │
│ • Detailed logging                      │
└─────────────────────────────────────────┘
```

---

## Monitoring Points

```
┌──────────────┐
│   /health    │──► Groq API status
│              │──► Cache size
│              │──► Timestamp
└──────────────┘

┌──────────────┐
│    /stats    │──► Cache size
│              │──► Timestamp
└──────────────┘

┌──────────────┐
│     Logs     │──► API call timing
│              │──► Cache hits/misses
│              │──► Parse failures
│              │──► Rate limit violations
│              │──► Error stack traces
└──────────────┘
```

---

**Architecture Version:** 2.0.0  
**Last Updated:** 2024-01-15  
**Status:** Production Ready ✅
