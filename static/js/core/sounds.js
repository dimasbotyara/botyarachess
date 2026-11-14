// Sound effects synthesised with WebAudio — no audio files needed, works
// fully offline. Respects the user's "sounds" setting.
let ctx = null;
let enabled = true;
let masterVolume = 0.7;

export function setSoundsEnabled(value) {
  enabled = !!value;
}

export function setVolume(percent) {
  masterVolume = Math.max(0, Math.min(1, (percent ?? 70) / 100));
}

function ensureCtx() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === 'suspended') ctx.resume().catch(() => {});
  return ctx;
}

/** Browsers block audio until a user gesture; unlock on first interaction. */
export function unlockAudio() {
  const handler = () => {
    ensureCtx();
    window.removeEventListener('pointerdown', handler);
  };
  window.addEventListener('pointerdown', handler);
}

function blip({ freq = 440, endFreq = null, duration = 0.08, type = 'sine',
                volume = 0.5, delay = 0 }) {
  const audio = ensureCtx();
  if (!audio || !enabled) return;
  const time = audio.currentTime + delay;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, time);
  if (endFreq) osc.frequency.exponentialRampToValueAtTime(endFreq, time + duration);
  gain.gain.setValueAtTime(0, time);
  gain.gain.linearRampToValueAtTime(volume * masterVolume, time + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, time + duration);
  osc.connect(gain).connect(audio.destination);
  osc.start(time);
  osc.stop(time + duration + 0.02);
}

export const sounds = {
  move() {
    blip({ freq: 290, endFreq: 180, duration: 0.07, type: 'triangle', volume: 0.45 });
  },
  capture() {
    blip({ freq: 180, endFreq: 90, duration: 0.11, type: 'square', volume: 0.35 });
  },
  castle() {
    blip({ freq: 260, endFreq: 200, duration: 0.06, type: 'triangle', volume: 0.4 });
    blip({ freq: 220, endFreq: 160, duration: 0.07, type: 'triangle', volume: 0.4, delay: 0.09 });
  },
  check() {
    blip({ freq: 760, duration: 0.09, type: 'sine', volume: 0.4 });
    blip({ freq: 920, duration: 0.11, type: 'sine', volume: 0.4, delay: 0.12 });
  },
  gameEnd() {
    blip({ freq: 523, duration: 0.16, type: 'sine', volume: 0.35 });
    blip({ freq: 659, duration: 0.16, type: 'sine', volume: 0.35, delay: 0.14 });
    blip({ freq: 784, duration: 0.28, type: 'sine', volume: 0.35, delay: 0.28 });
  },
  notify() {
    blip({ freq: 640, endFreq: 520, duration: 0.12, type: 'sine', volume: 0.3 });
  },
  illegal() {
    blip({ freq: 220, endFreq: 140, duration: 0.16, type: 'sawtooth', volume: 0.22 });
  },
};
