#pragma once

#include <juce_core/juce_core.h>

namespace apw
{

class EventEmitter final
{
public:
    explicit EventEmitter (const juce::String& host = "127.0.0.1", int port = 9876);
    ~EventEmitter() = default;

    void sendEvent (const juce::String& jsonEvent);

private:
    juce::DatagramSocket socket;
    juce::String targetHost;
    int targetPort;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (EventEmitter)
};

} // namespace apw
