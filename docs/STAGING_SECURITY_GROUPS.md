# PLUTO vProctor — Staging Security Group & Network Boundary Specification

**Document Version:** 1.1  
**Target Topology:** Option A — Single EC2 Instance (`g4dn.xlarge`)  
**Security Group Identifier:** `sg-pluto-staging`  
**Platform Version:** 0.1.0 (Release Candidate 1)  
**Date:** November 2026  

---

## 1. Network Perimeter & WebRTC Traffic Separation

PLUTO vProctor's real-time interview architecture utilizes three distinct network communication planes. Understanding the boundary between these planes is critical for defining the minimum necessary firewall rules:

```mermaid
flowchart TD
    subgraph Candidate Device [Remote Candidate Device (Any ISP / Corporate NAT)]
        C_Browser["Candidate Browser (React SPA + WebRTC Client)"]
    end

    subgraph Recruiter Device [Remote Recruiter Device (Office / Home)]
        R_Browser["Recruiter Browser (Admin Console + WebRTC Client)"]
    end

    subgraph AWS Cloud Perimeter: sg-pluto-staging
        subgraph Signaling Plane [WSS via Nginx Proxy]
            P443["TCP 443: HTTPS & WSS Signaling (/api/rooms/{id}/ws)"]
            P80["TCP 80: HTTP Redirect & ACME Challenge"]
        end

        subgraph Management Plane [Restricted Access]
            P22["TCP 22: SSH (Strictly Admin /32 CIDR)"]
        end

        subgraph Media Relay Plane: Coturn [Fallback for Symmetric NAT]
            P3478_UDP["UDP 3478: STUN & TURN Binding"]
            P3478_TCP["TCP 3478: TURN TCP Fallback"]
            P5349_TCP["TCP 5349: TURNS (TLS) Secure Relay"]
            P5349_UDP["UDP 5349: TURNS (DTLS) Secure Relay"]
            P_RELAY["UDP 49152-65535: Ephemeral Media Relay"]
        end

        subgraph Isolated Internal Subsystem [STRICTLY FORBIDDEN FROM PUBLIC INGRESS]
            BL_PG["TCP 5432: PostgreSQL (Docker Bridge Only)"]
            BL_REDIS["TCP 6379: Redis (Docker Bridge Only)"]
            BL_API["TCP 8000: FastAPI Backend (Docker Bridge Only)"]
            BL_AI["TCP 11434: Ollama Daemon (Docker Bridge Only)"]
        end
    end

    C_Browser -->|WSS Signaling (JSON)| P443
    R_Browser -->|WSS Signaling (JSON)| P443

    C_Browser <-->|Direct P2P Media (80-85% of Sessions - Zero Server Ingress)| R_Browser

    C_Browser -.->|Relay Media Stream (Symmetric NAT Fallback)| P3478_UDP
    C_Browser -.->|Strict Enterprise TLS Relay| P5349_TCP
    P_RELAY -.->|Relayed Media Packets| R_Browser
```

### 1.1 Plane 1: Control & Signaling Plane (WSS over TCP 443)
- **Role:** Handles room admission, authentication, SDP offer/answer exchange, ICE candidate trickling, chat, and proctoring telemetry (gaze/attention metrics at 2 Hz).
- **Transport:** WebSocket Secure (`wss://`) over standard **TCP port 443**.
- **Ingress Path:** Candidate browser -> Public EC2 IP (port 443) -> Nginx SSL termination -> Backend container (`http://backend:8000`).
- **Characteristics:** Low bandwidth (~2 kbps per participant). Standard HTTPS/WSS is allowed through virtually all corporate proxy servers and firewalls worldwide.

### 1.2 Plane 2: Direct Peer-to-Peer Media Plane (Dynamic UDP)
- **Role:** Streams bidirectional 720p 15fps WebM/VP8 video and 64 kbps Opus audio directly between candidate and recruiter browsers.
- **Transport:** Direct browser-to-browser encrypted WebRTC media over ephemeral UDP ports negotiated dynamically by ICE.
- **Server Impact:** **Zero bytes of media touch the EC2 server or Security Group.** In ~80–85% of consumer and standard office broadband networks, STUN discovers public IP mappings, and media flows directly peer-to-peer.

### 1.3 Plane 3: TURN Media Relay Plane (Coturn on EC2)
- **Role:** Required when either the candidate or recruiter is behind a strict enterprise firewall or symmetric NAT (which changes UDP port allocations dynamically, preventing direct P2P connections).
- **Transport:** Relayed through Coturn running on the EC2 host.
- **Ports Required for Coturn:**
  - **UDP 3478:** Primary STUN binding and standard TURN UDP media relay.
  - **TCP 3478:** TURN over TCP fallback for networks blocking outbound UDP.
  - **TCP 5349:** Secure TURNS over TLS. Encapsulates media in standard TLS on port 5349, bypassing deep packet inspection (DPI) firewalls.
  - **UDP 5349:** Secure TURNS over DTLS (Datagram Transport Layer Security).
  - **UDP 49152–65535 (or restricted range e.g. 49160–49200):** Dynamic port range allocated by Coturn to relay RTP/RTCP media packets between peers.

---

## 2. Inbound Security Group Rules (`sg-pluto-staging`)

Below is the definitive, minimum necessary inbound rule set for the staging EC2 instance:

| Rule Name | Protocol | Port Range | Source CIDR | Justification & Remote Candidate Support |
|---|---|---|---|---|
| **HTTP-Web** | TCP | `80` | `0.0.0.0/0` | Public web redirection to HTTPS. Mandatory for Let's Encrypt Certbot ACME HTTP-01 domain challenge verification. |
| **HTTPS-WSS** | TCP | `443` | `0.0.0.0/0` | Primary application entry point. Serves React SPA, REST API, and WebRTC WebSocket signaling (`/api/rooms/{id}/ws`). Supports all candidate browsers. |
| **SSH-Admin** | TCP | `22` | `ADMIN_OFFICE_IP/32` | Administrative shell access. **Strictly restricted to designated administrator IP address.** Must never be open to `0.0.0.0/0`. |
| **STUN-TURN-UDP**| UDP | `3478` | `0.0.0.0/0` | Standard STUN/TURN binding. Allows candidate browsers to discover external NAT mappings and initiate media relay requests. |
| **TURN-TCP** | TCP | `3478` | `0.0.0.0/0` | TURN TCP fallback. Allows candidates on networks blocking outbound UDP to establish relayed media sessions over TCP. |
| **TURNS-TLS** | TCP | `5349` | `0.0.0.0/0` | Secure TURN over TLS. Critical for enterprise candidates whose corporate proxies block unencrypted TURN traffic. |
| **TURNS-DTLS** | UDP | `5349` | `0.0.0.0/0` | Secure TURN over DTLS. Provides encrypted low-latency UDP media relay. |
| **TURN-Media-Relay**| UDP | `49160–49200` | `0.0.0.0/0` | Configured ephemeral relay port range in `turnserver.conf`. Allocates 2 UDP ports per active relayed interview stream (supports up to 20 concurrent streams). |

> [!TIP]
> **Restricting the UDP Relay Range:**  
> Rather than opening all 16,384 ports (`49152–65535`), configure `min-port=49160` and `max-port=49200` in `/etc/turnserver.conf`. This restricts the open firewall surface to just 41 UDP ports while comfortably supporting staging concurrency.

---

## 3. Outbound Security Group Rules (`sg-pluto-staging`)

| Protocol | Port Range | Destination CIDR | Justification & Operational Requirement |
|---|---|---|---|
| **TCP** | `443` | `0.0.0.0/0` | HTTPS egress for OS updates (`apt`), Docker image pulls, HuggingFace Faster-Whisper model cache download (`base.en`), Google STUN resolution, and S3 backup synchronization. |
| **TCP** | `80` | `0.0.0.0/0` | HTTP egress for Ubuntu package repository mirrors. |
| **UDP** | `49160–49200` | `0.0.0.0/0` | Egress media relay packets dispatched from Coturn back to remote candidate and recruiter browsers. |
| **UDP / TCP**| `53` | `0.0.0.0/0` | Domain Name System (DNS) resolution. |
| **UDP** | `123` | `0.0.0.0/0` | Network Time Protocol (NTP / chrony) clock synchronization. |

---

## 4. Forbidden Ingress Ports & Network Isolation Safeguards

> [!CAUTION]
> **Zero External Exposure for Internal Container Subsystems:**  
> The following four ports **MUST NEVER** appear in the AWS Security Group ingress rules:

1. **Port 5432 (PostgreSQL):** Must remain reachable only by the `backend` container on the internal Docker bridge network (`pluto_db_net`). Never map `5432:5432` to the host's public IP.
2. **Port 6379 (Redis):** Must remain bound strictly to the internal Docker network. Public exposure allows unauthenticated remote code execution or cache flushing.
3. **Port 8000 (FastAPI Uvicorn):** All traffic must traverse Nginx on port 443 to enforce rate limiting, request body limits (250 MB), and security headers. Direct access to port 8000 bypasses authentication proxies.
4. **Port 11434 (Ollama LLM):** Ollama does not implement built-in API key authentication. Exposing port 11434 to the internet allows any actor to run unauthorized inference or delete models.

---

## 5. Host Firewall Configuration Script (`ufw`)

As an additional layer of defense on the Ubuntu host, configure Uncomplicated Firewall (`ufw`):

```bash
#!/bin/bash
# /opt/scripts/configure_firewall.sh
set -euo pipefail

# Reset and set default policies
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow administrative SSH from specific IP only
sudo ufw allow from ADMIN_OFFICE_IP to any port 22 proto tcp comment "Admin SSH"

# Allow public web traffic
sudo ufw allow 80/tcp comment "HTTP Web & ACME"
sudo ufw allow 443/tcp comment "HTTPS Web & WSS Signaling"

# Allow Coturn WebRTC STUN/TURN traffic
sudo ufw allow 3478/udp comment "STUN & TURN UDP"
sudo ufw allow 3478/tcp comment "TURN TCP"
sudo ufw allow 5349/tcp comment "TURNS TLS"
sudo ufw allow 5349/udp comment "TURNS DTLS"
sudo ufw allow 49160:49200/udp comment "TURN Media Relay Range"

# Enable firewall
sudo ufw --force enable
sudo ufw status verbose
```
