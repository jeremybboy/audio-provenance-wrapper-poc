#include "EventEmitter.h"

namespace apw
{

EventEmitter::EventEmitter (const juce::String& host, int port)
    : targetHost (host),
      targetPort (port)
{
    socket.bindToPort (0);
}

void EventEmitter::sendEvent (const juce::String& jsonEvent)
{
    socket.write (targetHost, targetPort,
                  jsonEvent.toRawUTF8(),
                  static_cast<int> (jsonEvent.getNumBytesAsUTF8()));
}

} // namespace apw
