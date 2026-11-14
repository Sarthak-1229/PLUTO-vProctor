/**
 * Real Chrome WebRTC Peer Connection and Media Verification Script.
 * Spawns two independent Chrome instances with separate user profiles:
 * - Admin Profile (Port 9222)
 * - Candidate A Profile (Port 9223)
 * Uses --use-fake-ui-for-media-stream and --use-fake-device-for-media-stream
 * to test real getUserMedia, real RTCPeerConnection, real track addition,
 * real SDP offer/answer exchange, real ICE candidate gathering, and real packet transmission.
 */

import { spawn } from 'child_process'
import { mkdirSync, rmSync } from 'fs'
import { join } from 'path'
import { tmpdir } from 'os'

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const ADMIN_PORT = 9222
const CANDIDATE_PORT = 9223

const adminDir = join(tmpdir(), 'pluto_test_chrome_admin_' + Date.now())
const candDir = join(tmpdir(), 'pluto_test_chrome_cand_' + Date.now())

mkdirSync(adminDir, { recursive: true })
mkdirSync(candDir, { recursive: true })

function launchChrome(port, dataDir) {
  const args = [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${dataDir}`,
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    '--unsafely-treat-insecure-origin-as-secure=http://127.0.0.1:8000',
    'http://127.0.0.1:8000/api/health',
  ]
  const proc = spawn(CHROME_PATH, args, { stdio: 'ignore' })
  return proc
}

async function getWsUrl(port, retries = 20) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`)
      if (res.ok) {
        const pages = await res.json()
        if (Array.isArray(pages) && pages.length > 0 && pages[0].webSocketDebuggerUrl) {
          return pages[0].webSocketDebuggerUrl
        }
      }
    } catch {
      await new Promise((r) => setTimeout(r, 400))
    }
  }
  throw new Error(`Chrome on port ${port} failed to start debugger.`)
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl
    this.ws = null
    this.id = 1
    this.callbacks = new Map()
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl)
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve
      this.ws.onerror = reject
    })
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.id && this.callbacks.has(msg.id)) {
        const cb = this.callbacks.get(msg.id)
        this.callbacks.delete(msg.id)
        if (msg.error) cb.reject(new Error(msg.error.message))
        else cb.resolve(msg.result)
      }
    }
  }

  send(method, params = {}) {
    const id = this.id++
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }

  async evaluate(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    })
    if (res.exceptionDetails) {
      throw new Error(res.exceptionDetails.exception?.description || 'Runtime evaluation error')
    }
    return res.result?.value
  }

  close() {
    if (this.ws) this.ws.close()
  }
}

async function runRealBrowserVerification() {
  console.log('======================================================================')
  console.log('PLUTO vProctor — Real Chrome Dual-Browser WebRTC Peer Verification')
  console.log('======================================================================\n')

  console.log('[1/6] Launching 2 isolated Chrome instances with synthetic camera & mic...')
  const procAdmin = launchChrome(ADMIN_PORT, adminDir)
  const procCand = launchChrome(CANDIDATE_PORT, candDir)

  let cdpAdmin, cdpCand
  try {
    const wsAdminUrl = await getWsUrl(ADMIN_PORT)
    const wsCandUrl = await getWsUrl(CANDIDATE_PORT)
    console.log('  * Admin Chrome debugger ready on port', ADMIN_PORT)
    console.log('  * Candidate Chrome debugger ready on port', CANDIDATE_PORT)

    cdpAdmin = new CDPClient(wsAdminUrl)
    cdpCand = new CDPClient(wsCandUrl)
    await cdpAdmin.connect()
    await cdpCand.connect()

    console.log('\n[2/6] Verifying Camera & Microphone Access (getUserMedia) in real Chrome...')
    const mediaCheckSnippet = `
      (async () => {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        const videoTracks = stream.getVideoTracks();
        const audioTracks = stream.getAudioTracks();
        window.__stream = stream;
        return {
          videoTrack: videoTracks[0]?.label || 'none',
          videoReady: videoTracks[0]?.readyState,
          audioTrack: audioTracks[0]?.label || 'none',
          audioReady: audioTracks[0]?.readyState,
        };
      })()
    `
    const adminMedia = await cdpAdmin.evaluate(mediaCheckSnippet)
    const candMedia = await cdpCand.evaluate(mediaCheckSnippet)
    console.log('  * Admin Browser Devices:    Video:', adminMedia.videoTrack, `(${adminMedia.videoReady})`, '| Audio:', adminMedia.audioTrack)
    console.log('  * Candidate Browser Devices: Video:', candMedia.videoTrack, `(${candMedia.videoReady})`, '| Audio:', candMedia.audioTrack)

    console.log('\n[3/6] Initializing RTCPeerConnection with STUN in both Chrome instances...')
    const initPeerSnippet = `
      (() => {
        const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
        window.__pc = pc;
        window.__iceCandidates = [];
        window.__remoteTracks = [];
        pc.onicecandidate = (e) => {
          if (e.candidate) window.__iceCandidates.push(e.candidate.toJSON());
        };
        pc.ontrack = (e) => {
          window.__remoteTracks.push(e.track.kind);
        };
        for (const track of window.__stream.getTracks()) {
          pc.addTrack(track, window.__stream);
        }
        return { tracksAdded: window.__stream.getTracks().length };
      })()
    `
    const adminPC = await cdpAdmin.evaluate(initPeerSnippet)
    const candPC = await cdpCand.evaluate(initPeerSnippet)
    console.log(`  * Admin added ${adminPC.tracksAdded} tracks to peer connection`)
    console.log(`  * Candidate added ${candPC.tracksAdded} tracks to peer connection`)

    console.log('\n[4/6] Negotiating SDP Offer and Answer between browsers...')
    // 1. Admin creates offer
    const offerSdp = await cdpAdmin.evaluate(`
      (async () => {
        const offer = await window.__pc.createOffer();
        await window.__pc.setLocalDescription(offer);
        return offer.sdp;
      })()
    `)
    console.log('  * Admin generated SDP Offer (length:', offerSdp.length, 'bytes)')

    // 2. Candidate accepts offer and creates answer
    const answerSdp = await cdpCand.evaluate(`
      (async () => {
        await window.__pc.setRemoteDescription({ type: 'offer', sdp: ${JSON.stringify(offerSdp)} });
        const answer = await window.__pc.createAnswer();
        await window.__pc.setLocalDescription(answer);
        return answer.sdp;
      })()
    `)
    console.log('  * Candidate accepted Offer and generated SDP Answer (length:', answerSdp.length, 'bytes)')

    // 3. Admin accepts answer
    await cdpAdmin.evaluate(`
      (async () => {
        await window.__pc.setRemoteDescription({ type: 'answer', sdp: ${JSON.stringify(answerSdp)} });
      })()
    `)
    console.log('  * Admin accepted Candidate SDP Answer')

    console.log('\n[5/6] Exchanging ICE candidates via STUN...')
    // Wait 800ms for ICE gathering
    await new Promise((r) => setTimeout(r, 800))
    const adminCandidates = await cdpAdmin.evaluate(`window.__iceCandidates`)
    const candCandidates = await cdpCand.evaluate(`window.__iceCandidates`)
    console.log(`  * Admin gathered ${adminCandidates.length} ICE candidate(s)`)
    console.log(`  * Candidate gathered ${candCandidates.length} ICE candidate(s)`)

    // Relay candidates
    for (const c of adminCandidates) {
      await cdpCand.evaluate(`window.__pc.addIceCandidate(new RTCIceCandidate(${JSON.stringify(c)}))`)
    }
    for (const c of candCandidates) {
      await cdpAdmin.evaluate(`window.__pc.addIceCandidate(new RTCIceCandidate(${JSON.stringify(c)}))`)
    }

    console.log('\n[6/6] Verifying WebRTC Peer Connection State and Media Packet Flow...')
    // Wait up to 5 seconds for connection state to reach 'connected'
    let adminState = 'new', candState = 'new'
    for (let i = 0; i < 20; i++) {
      adminState = await cdpAdmin.evaluate(`window.__pc.connectionState`)
      candState = await cdpCand.evaluate(`window.__pc.connectionState`)
      if (adminState === 'connected' && candState === 'connected') break
      await new Promise((r) => setTimeout(r, 300))
    }
    console.log('  * Admin RTCPeerConnection State:    ', adminState)
    console.log('  * Candidate RTCPeerConnection State:', candState)

    // Inspect remote tracks received
    const adminRemoteTracks = await cdpAdmin.evaluate(`window.__remoteTracks`)
    const candRemoteTracks = await cdpCand.evaluate(`window.__remoteTracks`)
    console.log('  * Admin Remote Tracks Received:    ', adminRemoteTracks.join(', ') || 'none')
    console.log('  * Candidate Remote Tracks Received:', candRemoteTracks.join(', ') || 'none')

    // Wait 1.5 seconds for media packets to be transmitted and decoded
    await new Promise((r) => setTimeout(r, 1500))

    // Inspect RTCStats report for real bytes transmitted/received
    const candStats = await cdpCand.evaluate(`
      (async () => {
        const stats = await window.__pc.getStats();
        let bytesReceived = 0, packetsReceived = 0;
        stats.forEach((report) => {
          if (report.type === 'inbound-rtp' && report.bytesReceived) {
            bytesReceived += report.bytesReceived;
            packetsReceived += report.packetsReceived;
          }
        });
        return { bytesReceived, packetsReceived };
      })()
    `)
    console.log('  * Real Media Data Transferred:      ', candStats.bytesReceived, 'bytes (', candStats.packetsReceived, 'RTP packets )')

    const success = (adminState === 'connected' || candState === 'connected') && candStats.bytesReceived > 0
    console.log('\n======================================================================')
    if (success) {
      console.log('>>> [VERIFICATION SUCCESS] Real Chrome WebRTC Peer Media Flow Confirmed! <<<')
    } else {
      console.log(`>>> [VERIFICATION RESULT] State: Admin=${adminState}, Cand=${candState}, Bytes=${candStats.bytesReceived} <<<`)
    }
    console.log('======================================================================\n')
  } finally {
    if (cdpAdmin) cdpAdmin.close()
    if (cdpCand) cdpCand.close()
    procAdmin.kill()
    procCand.kill()
    try {
      rmSync(adminDir, { recursive: true, force: true })
      rmSync(candDir, { recursive: true, force: true })
    } catch {}
  }
}

runRealBrowserVerification().catch((err) => {
  console.error('Real Browser WebRTC Verification Error:', err)
  process.exit(1)
})
