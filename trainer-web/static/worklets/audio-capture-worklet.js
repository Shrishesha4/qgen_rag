// AudioWorklet file that runs in a separate context
class AudioCaptureWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.isCaptureActive = false;
    
    // Listen for messages from the main thread
    this.port.onmessage = (event) => {
      if (event.data.type === 'start-capture') {
        this.isCaptureActive = true;
      } else if (event.data.type === 'stop-capture') {
        this.isCaptureActive = false;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    if (!this.isCaptureActive) return true;

    const inputChannel = input[0];
    const outputData = new Float32Array(inputChannel);
    
    // Send the audio data back to the main thread
    this.port.postMessage({
      type: 'audio-data',
      data: outputData
    });

    return true;
  }
}

registerProcessor('audio-capture-worklet', AudioCaptureWorklet);
