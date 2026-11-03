const $ = (selector) => document.querySelector(selector);
const messages = $('#messages');
let speaking = false;
let recognition = null;
let busy = false;

function addMessage(role, content) {
  const element = document.createElement('div');
  element.className = `message ${role}`;
  const title = document.createElement('span');
  title.textContent = role === 'user' ? 'YOU' : 'JARVIS';
  const paragraph = document.createElement('p');
  paragraph.textContent = content; // never inject untrusted content as HTML
  element.append(title, paragraph);
  messages.append(element);
  messages.scrollTop = messages.scrollHeight;
}

function speak(text) {
  if (!speaking || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text.slice(0, 2000));
  utterance.rate = 0.95;
  utterance.pitch = 0.85;
  utterance.lang = 'en-IN';
  window.speechSynthesis.speak(utterance);
}

async function sendMessage(message) {
  if (busy || !message.trim()) return;
  busy = true;
  $('#send').disabled = true;
  addMessage('user', message);
  $('#state').textContent = 'PROCESSING REQUEST';
  try {
    const response = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({message})});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    addMessage('assistant', data.answer);
    $('#mode').textContent = data.mode === 'ai' ? 'AI MODE' : 'LOCAL MODE';
    speak(data.answer);
  } catch (_) {
    addMessage('assistant', 'Unable to reach the assistant service. Check that the server is running.');
  } finally {
    busy = false;
    $('#send').disabled = false;
    $('#state').textContent = 'READY FOR INPUT';
  }
}

$('#chat-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const message = $('#prompt').value.trim();
  if (!message || busy) return;
  $('#prompt').value = '';
  sendMessage(message);
});

$('#voice-toggle').addEventListener('click', () => {
  speaking = !speaking;
  $('#voice-toggle').textContent = speaking ? 'ON' : 'OFF';
  $('#voice-toggle').setAttribute('aria-pressed', String(speaking));
  if (!speaking && 'speechSynthesis' in window) window.speechSynthesis.cancel();
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  $('#voice-status').textContent = 'READY';
  recognition = new SpeechRecognition();
  recognition.lang = 'en-IN';
  recognition.interimResults = false;
  recognition.onstart = () => {$('#mic').classList.add('listening'); $('#state').textContent = 'LISTENING';};
  recognition.onend = () => {$('#mic').classList.remove('listening'); $('#state').textContent = 'READY FOR INPUT';};
  recognition.onerror = (event) => {addMessage('assistant', `Microphone unavailable (${event.error}). You can type instead.`);};
  recognition.onresult = (event) => {const text = event.results[0][0].transcript; sendMessage(text);};
  $('#mic').addEventListener('click', () => {if (busy) return; try {recognition.start();} catch (_) {recognition.stop();}});
} else {
  $('#voice-status').textContent = 'UNAVAILABLE';
  $('#mic').disabled = true;
  $('#mic').title = 'Speech recognition is not supported by this browser';
}

async function initialize() {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) throw new Error('Offline');
    const info = await response.json();
    $('#ai-status').textContent = info.ai_configured ? 'CONNECTED' : 'LOCAL';
  } catch (_) {$('#ai-status').textContent = 'OFFLINE';}
}
function tick() {$('#clock').textContent = new Date().toLocaleTimeString('en-GB', {hour12: false});}
tick(); setInterval(tick, 1000); initialize();
