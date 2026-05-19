#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

class AudioProvenanceCaptureAudioProcessor;

class AudioProvenanceCaptureAudioProcessorEditor final : public juce::AudioProcessorEditor
{
public:
    explicit AudioProvenanceCaptureAudioProcessorEditor (AudioProvenanceCaptureAudioProcessor&);
    ~AudioProvenanceCaptureAudioProcessorEditor() override = default;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    AudioProvenanceCaptureAudioProcessor& audioProcessor;
    juce::Label titleLabel;
    juce::Label statusLabel;
    juce::Label scopeLabel;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AudioProvenanceCaptureAudioProcessorEditor)
};
