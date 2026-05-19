#include "PluginEditor.h"
#include "PluginProcessor.h"

namespace
{
constexpr std::uint64_t activeTimeoutMilliseconds = 1000;

void configureObservationLabel (juce::Label& label, float fontSize)
{
    label.setJustificationType (juce::Justification::centredLeft);
    label.setFont (juce::FontOptions (fontSize));
}
}

AudioProvenanceCaptureAudioProcessorEditor::AudioProvenanceCaptureAudioProcessorEditor (
    AudioProvenanceCaptureAudioProcessor& processorRef)
    : AudioProcessorEditor (&processorRef),
      audioProcessor (processorRef)
{
    titleLabel.setText ("Audio Provenance Capture", juce::dontSendNotification);
    titleLabel.setJustificationType (juce::Justification::centredLeft);
    titleLabel.setFont (juce::FontOptions (20.0f, juce::Font::bold));
    addAndMakeVisible (titleLabel);

    configureObservationLabel (captureStatusLabel, 15.0f);
    addAndMakeVisible (captureStatusLabel);

    configureObservationLabel (audioDetectedLabel, 15.0f);
    addAndMakeVisible (audioDetectedLabel);

    configureObservationLabel (channelCountLabel, 15.0f);
    addAndMakeVisible (channelCountLabel);

    configureObservationLabel (sampleRateLabel, 15.0f);
    addAndMakeVisible (sampleRateLabel);

    configureObservationLabel (bufferSizeLabel, 15.0f);
    addAndMakeVisible (bufferSizeLabel);

    configureObservationLabel (lastBufferSeenLabel, 15.0f);
    addAndMakeVisible (lastBufferSeenLabel);

    scopeLabel.setText ("No hashing, UDP, C2PA, or wrapper-host logic in this build.", juce::dontSendNotification);
    scopeLabel.setJustificationType (juce::Justification::centredLeft);
    scopeLabel.setFont (juce::FontOptions (13.0f));
    addAndMakeVisible (scopeLabel);

    updateObservationLabels();
    startTimerHz (4);

    setSize (440, 250);
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
    captureStatusLabel.setBounds (bounds.removeFromTop (24));
    audioDetectedLabel.setBounds (bounds.removeFromTop (24));
    channelCountLabel.setBounds (bounds.removeFromTop (24));
    sampleRateLabel.setBounds (bounds.removeFromTop (24));
    bufferSizeLabel.setBounds (bounds.removeFromTop (24));
    lastBufferSeenLabel.setBounds (bounds.removeFromTop (24));
    bounds.removeFromTop (8);
    scopeLabel.setBounds (bounds.removeFromTop (28));
}

void AudioProvenanceCaptureAudioProcessorEditor::timerCallback()
{
    updateObservationLabels();
}

void AudioProvenanceCaptureAudioProcessorEditor::updateObservationLabels()
{
    const auto snapshot = audioProcessor.getAudioBufferObservationSnapshot();
    const auto nowMilliseconds = static_cast<std::uint64_t> (juce::Time::getMillisecondCounterHiRes());
    const auto hasRecentAudio = snapshot.lastNonSilentBufferSeenMilliseconds > 0
        && nowMilliseconds >= snapshot.lastNonSilentBufferSeenMilliseconds
        && nowMilliseconds - snapshot.lastNonSilentBufferSeenMilliseconds <= activeTimeoutMilliseconds;

    if (snapshot.lastBufferSeenMilliseconds > 0
        && snapshot.lastBufferSeenMilliseconds != lastRenderedBufferSeenMilliseconds)
    {
        lastRenderedBufferSeenMilliseconds = snapshot.lastBufferSeenMilliseconds;
        lastRenderedBufferSeenText = juce::Time::getCurrentTime().formatted ("%H:%M:%S");
    }

    captureStatusLabel.setText (juce::String ("Capture status: ") + (hasRecentAudio ? "ACTIVE" : "IDLE"),
                                juce::dontSendNotification);
    audioDetectedLabel.setText (juce::String ("Audio detected: ") + (hasRecentAudio ? "yes" : "no"),
                                juce::dontSendNotification);
    channelCountLabel.setText (juce::String ("Channels: ") + juce::String (snapshot.channelCount),
                               juce::dontSendNotification);
    sampleRateLabel.setText (juce::String ("Sample rate: ") + juce::String (snapshot.sampleRateHz) + " Hz",
                             juce::dontSendNotification);
    bufferSizeLabel.setText (juce::String ("Buffer size: ") + juce::String (snapshot.bufferSizeSamples) + " samples",
                             juce::dontSendNotification);
    lastBufferSeenLabel.setText (juce::String ("Last buffer seen: ") + lastRenderedBufferSeenText,
                                 juce::dontSendNotification);
}
