// State tracking
let isTalking = false;
let isBlinking = false;

const sprites = {
    idle: document.getElementById('state-idle'),
    talk: document.getElementById('state-talk'),
    blink: document.getElementById('state-blink'),
    talk_blink: document.getElementById('state-talk_blink')
};

function updateState() {
    // Hide all
    Object.values(sprites).forEach(el => el.classList.remove('active'));
    
    // Select active based on logic
    if (isTalking && isBlinking) {
        sprites.talk_blink.classList.add('active');
    } else if (isTalking) {
        sprites.talk.classList.add('active');
    } else if (isBlinking) {
        sprites.blink.classList.add('active');
    } else {
        sprites.idle.classList.add('active');
    }
}

// 1. Random Blink Loop
function blinkLoop() {
    const nextBlink = Math.random() * 4000 + 1000; // blink every 1-5 seconds
    setTimeout(() => {
        isBlinking = true;
        updateState();
        
        // Eyes closed for 150ms
        setTimeout(() => {
            isBlinking = false;
            updateState();
            blinkLoop();
        }, 150);
    }, nextBlink);
}
blinkLoop();

// 2. Microphone Input for Talking Detection
let audioContext = null;
let analyser = null;
let dataArray = null;

async function initMicrophone() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        
        const bufferLength = analyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);
        
        document.getElementById('mic-status').innerText = "마이크 감지 활성화 완료";
        setTimeout(() => {
            document.getElementById('mic-status').style.opacity = '0';
            setTimeout(() => {
                document.getElementById('mic-status').style.display = 'none';
            }, 500);
        }, 2000);
        
        detectVolume();
    } catch (err) {
        console.error("Microphone access denied or error:", err);
        document.getElementById('mic-status').innerText = "마이크 접근 실패 (클릭하여 재시도)";
    }
}

const TALK_VOLUME_THRESHOLD = 25; // Adjust sensitivity
let lastTalkTime = 0;

function detectVolume() {
    analyser.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }
    const average = sum / dataArray.length;
    
    const now = Date.now();
    if (average > TALK_VOLUME_THRESHOLD) {
        isTalking = true;
        lastTalkTime = now;
    } else if (now - lastTalkTime > 200) { // Keep mouth open for at least 200ms
        isTalking = false;
    }
    
    updateState();
    requestAnimationFrame(detectVolume);
}

// macOS security sandbox requires a user click/gesture to initialize audio
window.addEventListener('click', () => {
    if (!audioContext) {
        initMicrophone();
    }
});
window.addEventListener('dblclick', () => {
    if (!audioContext) {
        initMicrophone();
    }
});
