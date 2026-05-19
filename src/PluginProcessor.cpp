#include "PluginProcessor.h"
#include "PluginEditor.h"

AudioProvenanceCaptureAudioProcessor::AudioProvenanceCaptureAudioProcessor()
    : AudioProcessor (BusesProperties()
                          .withInput  ("Input",  juce::AudioChannelSet::stereo(), true)
                          .withOutput ("Output", juce::AudioChannelSet::stereo(), true))
{
}

void AudioProvenanceCaptureAudioProcessor::prepareToPlay (double, int)
{
}

void AudioProvenanceCaptureAudioProcessor::releaseResources()
{
}

bool AudioProvenanceCaptureAudioProcessor::isBusesLayoutSupported (const BusesLayout& layouts) const
{
    const auto& input = layouts.getMainInputChannelSet();
    const auto& output = layouts.getMainOutputChannelSet();

    if (input.isDisabled() || output.isDisabled())
        return false;

    if (input != output)
        return false;

    return input == juce::AudioChannelSet::mono()
        || input == juce::AudioChannelSet::stereo();
}

void AudioProvenanceCaptureAudioProcessor::processBlock (juce::AudioBuffer<float>& buffer,
                                                         juce::MidiBuffer& midiMessages)
{
    juce::ignoreUnused (midiMessages);
    passThrough (buffer);
}

void AudioProvenanceCaptureAudioProcessor::processBlock (juce::AudioBuffer<double>& buffer,
                                                         juce::MidiBuffer& midiMessages)
{
    juce::ignoreUnused (midiMessages);
    passThrough (buffer);
}

template <typename SampleType>
void AudioProvenanceCaptureAudioProcessor::passThrough (juce::AudioBuffer<SampleType>& buffer)
{
    const auto totalInputChannels = getTotalNumInputChannels();
    const auto totalOutputChannels = getTotalNumOutputChannels();

    for (auto channel = totalInputChannels; channel < totalOutputChannels; ++channel)
        buffer.clear (channel, 0, buffer.getNumSamples());
}

juce::AudioProcessorEditor* AudioProvenanceCaptureAudioProcessor::createEditor()
{
    return new AudioProvenanceCaptureAudioProcessorEditor (*this);
}

bool AudioProvenanceCaptureAudioProcessor::hasEditor() const
{
    return true;
}

const juce::String AudioProvenanceCaptureAudioProcessor::getName() const
{
    return JucePlugin_Name;
}

bool AudioProvenanceCaptureAudioProcessor::acceptsMidi() const
{
    return false;
}

bool AudioProvenanceCaptureAudioProcessor::producesMidi() const
{
    return false;
}

bool AudioProvenanceCaptureAudioProcessor::isMidiEffect() const
{
    return false;
}

double AudioProvenanceCaptureAudioProcessor::getTailLengthSeconds() const
{
    return 0.0;
}

int AudioProvenanceCaptureAudioProcessor::getNumPrograms()
{
    return 1;
}

int AudioProvenanceCaptureAudioProcessor::getCurrentProgram()
{
    return 0;
}

void AudioProvenanceCaptureAudioProcessor::setCurrentProgram (int)
{
}

const juce::String AudioProvenanceCaptureAudioProcessor::getProgramName (int)
{
    return {};
}

void AudioProvenanceCaptureAudioProcessor::changeProgramName (int, const juce::String&)
{
}

void AudioProvenanceCaptureAudioProcessor::getStateInformation (juce::MemoryBlock&)
{
}

void AudioProvenanceCaptureAudioProcessor::setStateInformation (const void*, int)
{
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new AudioProvenanceCaptureAudioProcessor();
}
