declare abstract class AudioWorkletProcessor {
	readonly port: MessagePort;
	constructor(options?: unknown);
	abstract process(
		inputs: Float32Array[][],
		outputs: Float32Array[][],
		parameters: Record<string, Float32Array>
	): boolean;
}

declare function registerProcessor(
	name: string,
	processorCtor: typeof AudioWorkletProcessor
): void;

class PcmCaptureProcessor extends AudioWorkletProcessor {
	process(inputs: Float32Array[][]): boolean {
		const channelData = inputs[0]?.[0];
		if (channelData && channelData.length > 0) {
			const copy = new Float32Array(channelData.length);
			copy.set(channelData);
			this.port.postMessage(copy);
		}

		return true;
	}
}

registerProcessor('pcm-capture-processor', PcmCaptureProcessor);

export {};