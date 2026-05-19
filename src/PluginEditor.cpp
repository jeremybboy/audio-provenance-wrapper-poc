#include "PluginEditor.h"
#include "PluginProcessor.h"

AudioProvenanceCaptureAudioProcessorEditor::AudioProvenanceCaptureAudioProcessorEditor (
    AudioProvenanceCaptureAudioProcessor& processorRef)
    : AudioProcessorEditor (&processorRef),
      audioProcessor (processorRef)
{
    juce::ignoreUnused (audioProcessor);

    titleLabel.setText ("Audio Provenance Capture", juce::dontSendNotification);
    titleLabel.setJustificationType (juce::Justification::centredLeft);
    titleLabel.setFont (juce::FontOptions (20.0f, juce::Font::bold));
    addAndMakeVisible (titleLabel);

    statusLabel.setText ("v0.1 pass-through VST3", juce::dontSendNotification);
    statusLabel.setJustificationType (juce::Justification::centredLeft);
    statusLabel.setFont (juce::FontOptions (15.0f));
    addAndMakeVisible (statusLabel);

    scopeLabel.setText ("No hashing, UDP, C2PA, or wrapper-host logic in this build.", juce::dontSendNotification);
    scopeLabel.setJustificationType (juce::Justification::centredLeft);
    scopeLabel.setFont (juce::FontOptions (13.0f));
    addAndMakeVisible (scopeLabel);

    setSize (420, 160);
}

void AudioProvenanceCaptureAudioProcessorEditor::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour::fromRGB (24, 26, 28));
    g.setColour (juce::Colour::fromRGB (70, 76, 82));
    g.drawRect (getLocalBounds(), 1);
}

void AudioProvenanceCaptureAudioProcessorEditor::resized()
{
    auto bounds = getLocalBounds().reduced (24);
    titleLabel.setBounds (bounds.removeFromTop (34));
    statusLabel.setBounds (bounds.removeFromTop (28));
    scopeLabel.setBounds (bounds.removeFromTop (28));
}
