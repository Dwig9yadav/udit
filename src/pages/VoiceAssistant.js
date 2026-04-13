import React, { useState, useRef, useEffect } from 'react';
import { ragAPI } from '../services/api';
import './VoiceAssistant.css';

const VoiceAssistant = () => {
    const [isRecording, setIsRecording] = useState(false);
    const [status, setStatus] = useState('Click the mic to start speaking');
    const [transcript, setTranscript] = useState('');
    const [answer, setAnswer] = useState('');
    const [loading, setLoading] = useState(false);
    const [isPlaying, setIsPlaying] = useState(false);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    // Initialize text-to-speech engine
    const synth = window.speechSynthesis;

    useEffect(() => {
        // Cleanup speech synthesis on unmount
        return () => {
            if (synth.speaking) {
                synth.cancel();
            }
        };
    }, []);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorderRef.current.onstop = handleAudioStop;
            
            mediaRecorderRef.current.start();
            setIsRecording(true);
            setStatus('Listening...');
            setTranscript('');
            setAnswer('');
            if (synth.speaking) synth.cancel();
        } catch (error) {
            console.error('Error accessing microphone:', error);
            setStatus('Microphone access denied. Please allow microphone permissions.');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
            setIsRecording(false);
            setStatus('Processing audio with Groq...');
        }
    };

    const handleAudioStop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setLoading(true);

        try {
            const response = await ragAPI.voiceSearch(audioBlob);
            setTranscript(response.transcript);
            
            if (response.generated_answer) {
                setAnswer(response.generated_answer);
                setStatus('Analysis complete.');
                playAudio(response.generated_answer);
            } else {
                setAnswer("I couldn't find an answer in your documents.");
                setStatus('Completed with no distinct answer.');
            }
        } catch (error) {
            console.error('Voice search failed:', error);
            setStatus(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const playAudio = (textToSpeak) => {
        if (!textToSpeak) return;
        
        if (synth.speaking) {
            synth.cancel();
        }

        const utterance = new SpeechSynthesisUtterance(textToSpeak);
        
        // Try to pick a natural English voice
        const voices = synth.getVoices();
        const englishVoice = voices.find(v => v.lang.includes('en-US')) || voices[0];
        if (englishVoice) {
            utterance.voice = englishVoice;
        }

        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onstart = () => setIsPlaying(true);
        utterance.onend = () => setIsPlaying(false);
        utterance.onerror = () => setIsPlaying(false);

        synth.speak(utterance);
    };

    const togglePlay = () => {
        if (isPlaying) {
            synth.cancel();
            setIsPlaying(false);
        } else if (answer) {
            playAudio(answer);
        }
    };

    return (
        <div className="voice-assistant-container">
            <div className="voice-header">
                <h2>🎙️ Groq Voice Assistant</h2>
                <p>Speak to search your notes instantly.</p>
            </div>

            <div className="voice-main-stage">
                <button 
                    className={`mic-button ${isRecording ? 'recording' : ''} ${loading ? 'loading' : ''}`}
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={loading}
                >
                    <span className="mic-icon">
                        {isRecording ? '⏹️' : '🎤'}
                    </span>
                    {isRecording && <div className="pulse-ring"></div>}
                </button>
                <div className="status-text">{status}</div>
            </div>

            <div className="voice-output-area">
                {transcript && (
                    <div className="transcript-box">
                        <span className="label">You said:</span>
                        <p>{transcript}</p>
                    </div>
                )}

                {answer && (
                    <div className="answer-box">
                        <div className="answer-header">
                            <span className="label">EduRag AI:</span>
                            <button 
                                className={`play-button ${isPlaying ? 'playing' : ''}`}
                                onClick={togglePlay}
                            >
                                {isPlaying ? '🛑 Stop Audio' : '🔊 Play Sound'}
                            </button>
                        </div>
                        <div className="answer-content">
                            <p dangerouslySetInnerHTML={{ __html: answer.replace(/\n\n/g, '<br/><br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}></p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default VoiceAssistant;
