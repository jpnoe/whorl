// Exercises the actual sketch with simulated I/O. Not a board build or timing test.
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>

constexpr int HIGH = 1;
constexpr int LOW = 0;
constexpr int INPUT_PULLUP = 2;
unsigned long clockMicros = 0;
int sensorState = HIGH;
unsigned long micros() { return clockMicros; }
unsigned long millis() { return clockMicros / 1000; }
void pinMode(uint8_t, int) {}
int digitalRead(uint8_t) { return sensorState; }
struct SerialStub {
  void begin(int) {}
  explicit operator bool() const { return true; }
  template<class T> void print(T) {}
  template<class T> void println(T) {}
  void println(float, int) {}
} Serial;

#include "../firmware/whorl/whorl.ino"

void resetTest() {
  resetMotionTracking();
  previousState = HIGH;
  lastMidiValue = -1;
  sensorState = HIGH;
}

void pulse(unsigned long when) {
  clockMicros = when;
  sensorState = LOW;
  loop();
  sensorState = HIGH;
  clockMicros = when + 10;
  loop();
}

int main() {
  assert(rpmToMidi(0) == 0 && rpmToMidi(50) == 0);
  assert(rpmToMidi(300) == 64 && rpmToMidi(550) == 127 && rpmToMidi(900) == 127);

  resetTest();
  assert(getStopTimeout() == MAX_STOP_TIMEOUT_US);
  lastRevolutionMicros = 50000;
  assert(getStopTimeout() == MIN_STOP_TIMEOUT_US);
  lastRevolutionMicros = 2000000;
  assert(getStopTimeout() == MAX_STOP_TIMEOUT_US);

  resetTest();
  pulse(100000);
  pulse(100500);
  assert(pulseCount == 1); // Sub-debounce falling edge ignored.

  resetTest();
  pulse(100000);
  pulse(200000);
  assert(!hasSmoothedRpm);
  pulse(300000);
  assert(hasSmoothedRpm && std::abs(smoothedRpm - 300.0f) < 0.01f);
  assert(lastRevolutionMicros == 200000 && lastMidiValue == 64);
  clockMicros = 501000;
  loop();
  assert(lastMidiValue == 0 && pulseCount == 0 && !hasSmoothedRpm);
  std::cout << "Firmware host checks passed: mapping, adaptive timeout, debounce, full-revolution estimate, and stop reset.\n";
}
