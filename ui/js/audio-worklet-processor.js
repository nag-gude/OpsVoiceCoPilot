/* AudioWorklet processor for Ops Voice Co-Pilot.
 * Captures mono PCM float32 frames and posts them back to the main thread.
 */

class OpsVoiceProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length) {
      // Send the mono channel samples back to the main thread.
      this.port.postMessage(input[0]);
    }
    // Keep processor alive.
    return true;
  }
}

registerProcessor('ops-voice-processor', OpsVoiceProcessor);

