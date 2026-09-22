# FACTORY-A Orchestrator — Production Line Book
> Version: 1.0  
> Path: `C:\Factory_a\`  
> Status: Infrastructure COMPLETE — Phase Next = Full Autonomous API

---

## 1. ระบบนี้คืออะไร

โรงงานผลิต Code อัตโนมัติโดย AI Council หลายตัวทำงานเป็น pipeline

```
Input  : Joe ใส่ module name + spec documents
Output : Code ผ่าน G-Score ≥ 0.99 พร้อม integrate ทันที
Joe    : ทำแค่อย่างเดียว = กด APPROVE INTEGRATE
```

เป้าหมายสุดท้าย: Joe เปิด app — กด START — ไปฟิตเนส — กลับมาดูผล

---

## 2. Council Nodes — ใครทำอะไร

| Node | ชื่อ | หน้าที่ | ตัดสินใจเอง |
|------|------|---------|-------------|
| **S1-W** | Watcher / Orchestrator | monitor files, route signals ระหว่าง nodes | ✅ route PASS/FAIL |
| **S1-SA** | Senior Analyst | chain verify, เขียน Decision Card, alert Joe | ✅ ยกเว้น approve integrate |
| **S2-A** | Senior Architect | ออก command.json ให้ S3, QC output, route fix | ✅ fix minor ไม่ต้องถาม Joe |
| **S2-B** | Builder / Spec Reviewer | review GOLDEN_IO_LOCK, REASON_CODES, เขียน verdict.json | ✅ ถาม S2-A เท่านั้น |
| **S3** | Build Engine | รัน AIEL-0→1→2→3, loop fix เอง | ✅ ยกเว้น LAW violation |

### Delegation Rules (ห้ามถาม Joe)

```
S2-B แก้ I/O, REASON_CODES    → ถาม S2-A เท่านั้น
Test file ผิด structure        → S1-W + S1-SA จัดการเอง
S3 AIEL loop fail              → S3 loop fix เอง
G-Score < 0.99                 → S2-A + S3 loop เอง
Schema wiring mismatch         → S1-SA วินิจฉัย + สั่ง fix
Report chain mismatch          → S1-SA จัดการ

Joe ตัดสินใจเฉพาะ:
  ✅ APPROVE INTEGRATE
  ✅ Phase transition
  ✅ Reject / Rollback module
```

---

## 3. Pipeline Flow

```
Joe ใส่ module name + spec
         │
         ▼
    ┌─────────────┐
    │    S2-B     │  review spec
    │ SPEC REVIEW │  GOLDEN_IO_LOCK, REASON_CODES
    └─────────────┘
         │
    ┌────┴────────────────┐
    │                     │
  PASS               FAIL MAJOR
    │                     │
    │              [JOE ALERT] ← เดียวที่ Joe เห็น
    ▼
    ┌─────────────┐
    │    S2-A     │  issue command.json
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │     S3      │  AIEL-0 → 1 → 2 → 3
    │ BUILD ENGINE│  loop fix เองถ้า fail
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │   S1-SA     │  chain verify (4 report files)
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │   S1-SA     │  เขียน Decision Card
    └─────────────┘
         │
         ▼
════════════════════════════════
  [JOE ACTION REQUIRED]
  module: <name>
  G-Score: 1.0000
  Tests: N/N PASS
  → กด APPROVE INTEGRATE
════════════════════════════════
         │
         ▼
  integrate_single_m.py
  integrate.py
         │
         ▼
  ✅ CERTIFIED  G-Score 1.0000
```

---

## 4. AIEL Pipeline (S3 Build Engine)

```
AIEL-0  Raw code generation     ← สร้างโครงแรก
AIEL-1  Structure refactor      ← เพิ่ม type hints, structure
AIEL-2  Optimize + harden       ← performance, error handling
AIEL-3  Polish + verify         ← docs, tests, final QC

G-Score threshold: ≥ 0.99
ถ้าไม่ผ่าน → loop กลับ AIEL-2 อัตโนมัติ
```

---

## 5. Infrastructure ที่ Build แล้ว

```
C:\Factory_a\
├── watcher.py              ← single process, relay ทุก node ในตัวเดียว
│                             poll ทุก 10s, broadcast STAGE_CHANGE
├── council_relay.py        ← message bus core
├── council_relay.json      ← shared message queue (audit log)
├── dashboard_server.py     ← HTTP server localhost:8080
│                             อ่านไฟล์จริง, auto-refresh ทุก 3s
└── outputs/reports/
    ├── workflow_status.json      ← pipeline state (SSOT)
    └── <module>/
        ├── verdict.json          ← S2-B output
        ├── run_report.json       ← S3 output
        └── <module>_final_status.json
```

### Message Flow (council_relay.json)

```json
{
  "from": "s3",
  "to": "s2a",
  "module": "brain_router",
  "stage": "AIEL-3",
  "status": "READY",
  "requires_action": true
}
```

---

## 6. รัน System

```powershell
# Terminal 1 — pipeline engine (ทิ้งไว้ตลอด session)
cd C:\Factory_a
python watcher.py

# Terminal 2 — dashboard
cd C:\Factory_a
python dashboard_server.py
# browser เปิดเองที่ localhost:8080
```

---

## 7. Dashboard (localhost:8080)

แสดง 4 sections อ่านไฟล์จริงทุก 3 วินาที:

```
1. WORKFLOW STATUS   ← pipeline อยู่ stage ไหน, module ปัจจุบัน
2. MODULE LIST       ← G-Score, tests pass, status ทุก module
3. RELAY LOG         ← node คุยกันยังไง (last 20 messages)
4. HEALTH CHECK      ← files ครบไหม, size
```

---

## 8. Modules ที่ Certified แล้ว

| Module | Tests | G-Score | Status |
|--------|-------|---------|--------|
| ea3_logger | — | 1.0000 | ✅ CERTIFIED |
| ea2_logger | — | 1.0000 | ✅ CERTIFIED |
| run_continuous | 151/151 | 1.0000 | ✅ CERTIFIED |
| live_runner_continuous | 138/138 | 1.0000 | ✅ CERTIFIED |
| brain_router | 7/7 | — | ✅ INTEGRATED |
| guard | — | — | 🔄 In Progress |

---

## 9. บทเรียนสำคัญ

```
❌ relay_node.py แยก process = เปิด 10 หน้าต่าง ใช้ไม่ได้
✅ Fix: merge เข้า watcher.py process เดียว

❌ AI ใน VSCode = passive ต้องมีคน trigger ตลอด
✅ Fix จริง: ใช้ Claude API แทน
   watcher.py เรียก API เองได้ ไม่ต้องมีคน

❌ Dashboard อ่าน local file จาก browser ตรงๆ ไม่ได้
✅ Fix: dashboard_server.py serve HTTP

❌ start python relay_node.py S1-W ใน PowerShell ไม่ทำงาน
✅ Fix: Start-Process -FilePath python -ArgumentList "relay_node.py","S1-W"
```

---

## 10. Next Phase — Full Autonomous

เป้าหมาย: Joe กด START แล้วไปได้เลย ไม่ต้อง paste อะไร

```
Architecture ปัจจุบัน (Semi-Auto):
  Joe → VSCode paste → AI respond → Joe paste ต่อ → ...

Architecture เป้าหมาย (Full Auto):
  Joe กด START
      │
      ▼
  watcher.py เรียก Claude API โดยตรง
  แต่ละ node = API call พร้อม system prompt
      │
      ▼
  pipeline วิ่งเอง node ต่อ node
      │
      ▼
  [JOE ACTION REQUIRED] แค่ครั้งเดียว
  → กด APPROVE บน dashboard
      │
      ▼
  integrate.py รันเอง
  ✅ DONE
```

### สิ่งที่ต้องทำ

```
1. แก้ watcher.py ให้เรียก Anthropic API
   - แต่ละ node = function ที่เรียก API พร้อม system prompt
   - S2-B, S3, S1-SA เป็น API calls ไม่ใช่ VSCode sessions

2. Dashboard upgrade
   - UI แบบ index.html (dark theme, node cards, log panel)
   - ปุ่ม APPROVE เดียว
   - Mode selector: AUTO / STEP / CHAT

3. CHAT mode
   - Joe เลือก node ที่ต้องการคุย
   - ส่ง message ไปหา node นั้นโดยตรง
   - node ตอบกลับผ่าน dashboard

4. Absolute mode (สั่งตัวเองได้)
   - node สั่ง spawn sub-nodes เพิ่มได้
   - 2 nodes คุยกันเองแล้วรายงาน Joe
   - Joe ไม่ต้อง approve ระหว่างทาง
```

---

## 11. File References สำคัญ

```
System Prompts:
  C:\Factory_a\S3_SYSTEM_PROMPT_FACTORY_A_v2_6.md
  C:\Factory_a\S1_HIGH_COUNCIL_META.md
  C:\Factory_a\S2A_SYSTEM_PROMPT.md

SSOT:
  C:\Factory_a\PYTHONBRAIN_SSOT_HYBRID_vFinal.md

Pipeline State:
  C:\Factory_a\outputs\reports\workflow_status.json

Audit Log:
  C:\Factory_a\council_relay.json
```

---

*Production Line Book v1.0 — compiled from Factory-A build sessions*
