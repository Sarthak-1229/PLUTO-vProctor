# PLUTO vProctor — Zoho-First Live Interview & WebRTC Architecture

**Document Version:** 1.0  
**Target Platform:** Zoho Catalyst (AppSail & Web Client Hosting) + External TURN Relay  
**Date Checked:** November 16, 2026  
**Status:** ARCHITECTURAL DESIGN & TOPOLOGY SPECIFICATION (Zero Infrastructure Provisioned)  

---

## 1. Executive Summary

PLUTO vProctor's hosted interview rooms require low-latency, synchronized communication across three distinct network planes:
1. **Control & Signaling Plane:** Room admission, state transitions (`LOBBY` -> `LIVE` -> `PAUSED` -> `COMPLETED`), question progression, real-time gaze telemetry at 2 Hz, and WebRTC SDP/ICE exchange.
2. **Peer-to-Peer Media Plane:** Direct browser-to-browser WebRTC video (720p 15fps VP8) and audio (64 kbps Opus).
3. **Media Relay Plane (TURN):** Fallback packet relaying when candidate or recruiter firewalls utilize symmetric NAT.

This document designs a robust live interview architecture on Zoho Catalyst, explicitly accounts for Catalyst's WebSocket and network constraints, and compares three candidate deployment topologies.

---

## 2. Network Plane Analysis on Zoho Catalyst

```mermaid
flowchart TD
    subgraph Remote Candidate Device
        C_Browser["Candidate Browser (React SPA + WebRTC)"]
    end

    subgraph Remote Recruiter Device
        R_Browser["Recruiter Browser (Admin Console + WebRTC)"]
    end

    subgraph Zoho Catalyst Cloud Boundary
        FE["Web Client Hosting (React Static SPA + CDN)"]
        AppSail["Catalyst AppSail (FastAPI ASGI Backend)<br>Persistent Single Instance (min=1, max=1)<br>Hosts RoomConnectionManager (/api/rooms/{id}/ws)"]
    end

    subgraph External Infrastructure: AWS ap-south-1
        DB[("Managed PostgreSQL 16<br>(AWS RDS / Supabase)")]
        Coturn["Minimal Coturn Relay VM<br>(AWS t4g.nano in ap-south-1)<br>UDP/TCP 3478, TCP 5349, UDP 49160-49200"]
    end

    C_Browser -->|HTTPS GET: Fetch Web SPA| FE
    R_Browser -->|HTTPS GET: Fetch Admin SPA| FE

    C_Browser <==>|Plane 1: WSS WebSocket Signaling (TCP 443)| AppSail
    R_Browser <==>|Plane 1: WSS WebSocket Signaling (TCP 443)| AppSail
    AppSail <-->|Persist Session State| DB

    C_Browser <-.->|Plane 2: Direct P2P Media (80-85% of Sessions - Zero Server Ingress)| R_Browser

    C_Browser -.->|Plane 3: Relayed Media RTP (Symmetric NAT Fallback)| Coturn
    Coturn -.->|Plane 3: Relayed Media RTP| R_Browser
```

### 2.1 Plane 1: Control & Signaling Plane (WSS over TCP 443)
- **Catalyst Functions Incompatibility:** Catalyst Serverless Functions (Basic/Advanced I/O) **do not support persistent WebSockets**. Functions terminate execution upon returning an HTTP response.
- **Catalyst AppSail Capability:** AppSail supports persistent WebSocket connections on containerized runtimes (Python/FastAPI).
- **The Process-Local State Challenge:**  
  PLUTO’s `RoomConnectionManager` (`backend/app/services/realtime/connection_manager.py`) manages active WebSockets in a process-local Python dictionary (`self._rooms: Dict[str, Dict[str, Any]] = {}`).
  - If AppSail is allowed to auto-scale horizontally to multiple container instances, incoming WebSockets are load-balanced across separate instances. A candidate connected to Instance A cannot receive room events dispatched by an interviewer connected to Instance B!
- **Staging Resolution:**  
  For staging validation, configure AppSail with **`min-instances=1` and `max-instances=1`**. A single persistent 1 GB or 2 GB AppSail container can comfortably handle hundreds of concurrent WebSocket signaling connections while maintaining unified in-memory room state.

### 2.2 Plane 2: Direct Peer-to-Peer Media Plane (Dynamic UDP)
- **Direct Browser Communication:** In 80–85% of interview sessions (standard residential broadband, 4G/5G mobile networks, and non-restrictive office networks), Google STUN (`stun:stun.l.google.com:19302`) discovers the public reflexive IP addresses of both peers.
- **Zero Server Overhead:** Media packets stream directly between the candidate and recruiter browsers using DTLS-SRTP. **Zero bytes of media stream through Zoho Catalyst**, resulting in zero bandwidth cost and minimum network latency.

### 2.3 Plane 3: Media Relay Plane (TURN / Coturn)
- **The Symmetric NAT Problem:** When a candidate or recruiter operates behind a strict enterprise firewall or corporate proxy, symmetric NAT changes UDP port bindings dynamically per destination, preventing direct P2P connections.
- **Catalyst Platform Boundary:** **Zoho Catalyst cannot host a Coturn TURN server.** Catalyst AppSail and serverless runtimes do not expose arbitrary UDP port ranges (`49160–49200`) or provide the raw socket bindings required by RFC 5766 / RFC 8656.
- **Architectural Requirement:** A dedicated external Coturn instance with a public IPv4 address is mandatory for symmetric NAT traversal.

---

## 3. Comparison of Candidate Deployment Topologies

To identify the optimal deployment structure for PLUTO vProctor, three architectural configurations were evaluated:

```mermaid
flowchart LR
    subgraph Topology 1: Pure Catalyst
        T1_FE["Web Client Hosting"]
        T1_API["AppSail API"]
        T1_AI["QuickML"]
        T1_ST["Stratus"]
        T1_DB["External DB"]
        T1_STUN["STUN Only"]
    end

    subgraph Topology 2: Catalyst + Minimal External TURN (Recommended)
        T2_FE["Web Client Hosting"]
        T2_API["AppSail API & WSS"]
        T2_AI["QuickML"]
        T2_ST["Stratus"]
        T2_DB["External DB (ap-south-1)"]
        T2_TURN["AWS t4g.nano Coturn (ap-south-1)"]
    end

    subgraph Topology 3: Hybrid Catalyst + AWS GPU
        T3_FE["Web Client Hosting"]
        T3_API["AppSail API"]
        T3_AI["AWS EC2 g4dn.xlarge (GPU)"]
        T3_TURN["AWS Coturn"]
        T3_DB["AWS RDS"]
    end
```

### 3.1 Detailed Topology Comparison Matrix

| Evaluation Dimension | Topology 1: Pure Catalyst | Topology 2: Catalyst + Minimal External TURN (Recommended) | Topology 3: Hybrid Catalyst + AWS GPU |
|---|---|---|---|
| **Web UI Hosting** | Catalyst Web Client Hosting | Catalyst Web Client Hosting | Catalyst Web Client Hosting |
| **API & Signaling** | Catalyst AppSail (Single Instance) | Catalyst AppSail (Single Instance) | Catalyst AppSail (Single Instance) |
| **Relational Database** | External Managed DB (Free Tier / Neon) | External Managed DB (AWS RDS / Supabase in `ap-south-1`) | AWS RDS PostgreSQL 16 (`ap-south-1`) |
| **Object Storage** | Catalyst Stratus (Zero Egress) | Catalyst Stratus (Zero Egress) | Catalyst Stratus (Zero Egress) |
| **LLM Inference** | Catalyst QuickML (`qwen2.5:3b`) | Catalyst QuickML (`qwen2.5:3b`) | AWS EC2 GPU (Ollama on `g4dn.xlarge`) |
| **ASR Speech-to-Text** | Cloud ASR API (Deepgram) | Cloud ASR API (Deepgram) or External Worker | Local Faster-Whisper on AWS EC2 |
| **WebRTC Traversal** | **Public STUN Only (No TURN)** | **External Coturn VM (AWS `t4g.nano` in `ap-south-1`)** | Coturn running on AWS EC2 GPU instance |
| **Symmetric NAT Handling** | **FAILS (15-20% of sessions fail)** | **SUCCEEDS (100% NAT traversal)** | **SUCCEEDS (100% NAT traversal)** |
| **Monthly Cost (8h/day)** | **~$5.00 – $8.00 / month** | **~$12.00 – $18.00 / month** | **~$110.00 – $130.00 / month** |
| **Catalyst Credit Burn** | Uses $250 credits for AppSail & QuickML | Uses $250 credits for AppSail & QuickML | Uses $250 credits for AppSail only |
| **Out-of-Pocket Cash** | **$0.00** (Full credit absorption) | **~$6.85 / month** (AWS RDS + EC2 nano) | **~$105.00 / month** (AWS GPU EC2) |
| **Code Refactoring** | QuickML adapter only | QuickML adapter only | Zero code changes (uses Ollama) |
| **Staging Suitability** | Inadequate (Fails on enterprise NAT) | **OPTIMAL (Full enterprise capability at minimal cost)** | Over-budget (Exceeds $80/mo target) |

---

## 4. In-Depth Analysis of Topology 2 (Recommended Staging Model)

### 4.1 Why Topology 2 is Optimal
1. **100% WebRTC Traversal Reliability:**  
   Unlike Topology 1 (which relies strictly on public STUN and fails whenever a candidate connects from a corporate network, university Wi-Fi, or restrictive ISP), Topology 2 guarantees media connectivity via the external Coturn instance.
2. **Strict Budget Adherence ($80/month target):**  
   - Catalyst AppSail, Web Client Hosting, Stratus, and QuickML are **100% absorbed by the $250 Catalyst credits** during staging.
   - The external AWS infrastructure consists only of:
     - 1x AWS EC2 `t4g.nano` (ARM64, 2 vCPU, 0.5 GiB RAM) running Coturn: **~$3.06/month** (for 8h/day schedule).
     - 1x AWS RDS `db.t4g.micro` PostgreSQL 16: **~$4.38/month** (for 8h/day schedule) or **$0.00** if using Supabase free tier.
     - Out-of-pocket cash: **~$7.44/month**, far below the $80/month budget cap!
3. **Low Latency (< 15ms):**  
   Placing both the database and the TURN server in **AWS ap-south-1 (Mumbai)** ensures ultra-low latency to Zoho Catalyst’s India infrastructure.

---

## 5. Room State Synchronization & Lifecycle Protocol

To guarantee smooth room management across AppSail:

```mermaid
sequenceDiagram
    autonumber
    participant CB as Candidate Browser
    participant IB as Interviewer Browser
    participant AS as AppSail FastAPI (Port 443)
    participant CT as Coturn Relay (ap-south-1)
    participant DB as Managed PostgreSQL

    Note over IB,AS: 1. Room Scheduling
    IB->>AS: POST /api/rooms (Schedule Room)
    AS->>DB: INSERT INTO interview_rooms (status=LOBBY)
    AS-->>IB: Room Code & Secret Tokens

    Note over CB,AS: 2. Signaling Admission & ICE Exchange
    CB->>AS: WSS Connect (/api/rooms/{id}/ws?token=...)
    IB->>AS: WSS Connect (/api/rooms/{id}/ws?token=...)
    AS-->>CB: Room Snapshot (ice_servers: STUN + Coturn ap-south-1)
    AS-->>IB: Room Snapshot (ice_servers: STUN + Coturn ap-south-1)

    Note over CB,IB: 3. Media Negotiation
    CB->>AS: WebSocket: send 'offer' (SDP)
    AS->>IB: WebSocket: relay 'offer'
    IB->>AS: WebSocket: send 'answer' (SDP)
    AS->>CB: WebSocket: relay 'answer'
    CB->>AS: WebSocket: trickle 'ice_candidate'
    AS->>IB: WebSocket: relay 'ice_candidate'

    alt Direct P2P Available
        CB<->IB: Direct Encrypted Video/Audio (UDP)
    else Symmetric NAT Detected
        CB->>CT: Allocate Relay Port (UDP 49160-49200)
        IB->>CT: Connect to Relay Port
        CB<->CT<->IB: Relayed Media Stream (RTP)
    end

    Note over CB,AS: 4. Real-time Proctoring Telemetry
    CB->>AS: WebSocket: gaze_telemetry (yaw, pitch, eye_contact at 2 Hz)
    AS->>AS: Monotonic timeline aggregation (in memory)
```

### 5.1 Reconnection & Network Disruption Handling
- **Heartbeat & Ping/Pong:** The client browser sends a ping frame every 15 seconds. If a connection drops, the React client automatically re-establishes the WebSocket connection within 3 seconds.
- **State Hydration:** When reconnecting, `RoomConnectionManager` queries the PostgreSQL database (`interview_rooms`), restores the candidate's active stage, and emits the latest room state.
- **ICE Restart:** If media drops while signaling remains alive, the client invokes `pc.createOffer({ iceRestart: true })`, renegotiating candidate pairs without interrupting the interview session.
