constexpr uint8_t HALL_PIN = 2;
constexpr uint8_t MAGNET_COUNT = 2;

constexpr float MIN_RPM = 50.0;
constexpr float MAX_RPM = 550.0;

constexpr unsigned long DEBOUNCE_US = 2000;
constexpr unsigned long MIN_STOP_TIMEOUT_US = 100000;
constexpr unsigned long MAX_STOP_TIMEOUT_US = 1500000;
constexpr float STOP_TIMEOUT_MULTIPLIER = 1.0;
unsigned long lastRevolutionMicros = 0;

constexpr float EMA_ALPHA = 0.30;

int previousState = HIGH;

unsigned long pulseCount = 0;
unsigned long pulseTimes[MAGNET_COUNT] = {0, 0};
unsigned long lastPulseMicros = 0;

int lastMidiValue = -1;
float smoothedRpm = 0.0;
bool hasSmoothedRpm = false;

unsigned long getStopTimeout() {
  if (lastRevolutionMicros == 0) {
    return MAX_STOP_TIMEOUT_US;
  }

  unsigned long adaptiveTimeout =
    static_cast<unsigned long>(
      lastRevolutionMicros * STOP_TIMEOUT_MULTIPLIER
    );

  if (adaptiveTimeout < MIN_STOP_TIMEOUT_US) {
    return MIN_STOP_TIMEOUT_US;
  }

  if (adaptiveTimeout > MAX_STOP_TIMEOUT_US) {
    return MAX_STOP_TIMEOUT_US;
  }

  return adaptiveTimeout;
}

int rpmToMidi(float rpm) {
  if (rpm <= MIN_RPM) {
    return 0;
  }

  if (rpm >= MAX_RPM) {
    return 127;
  }

  float normalized =
    (rpm - MIN_RPM) / (MAX_RPM - MIN_RPM);

  return static_cast<int>(
    normalized * 127.0 + 0.5
  );
}

void sendControllerValue(int value, float rpm) {
  if (value == lastMidiValue) {
    return;
  }

  // Machine-readable output for our upcoming Mac bridge.
  Serial.print("CC,74,");
  Serial.print(value);
  Serial.print(",RPM,");
  Serial.println(rpm, 1);

  lastMidiValue = value;
}

void resetMotionTracking() {
  pulseCount = 0;
  pulseTimes[0] = 0;
  pulseTimes[1] = 0;
  lastPulseMicros = 0;

  smoothedRpm = 0.0;
  hasSmoothedRpm = false;
  lastRevolutionMicros = 0;
}

void setup() {
  Serial.begin(115200);
  pinMode(HALL_PIN, INPUT_PULLUP);

  while (!Serial && millis() < 3000) {
  }

  Serial.println("Spinner MIDI-value test ready");
  sendControllerValue(0, 0.0);
}

void loop() {
  int currentState = digitalRead(HALL_PIN);
  unsigned long now = micros();

  if (previousState == HIGH && currentState == LOW) {
    if (
      lastPulseMicros == 0 ||
      now - lastPulseMicros > DEBOUNCE_US
    ) {
      uint8_t slot = pulseCount % MAGNET_COUNT;

      // Compare each magnet with itself one revolution later.
      if (pulseCount >= MAGNET_COUNT) {
        unsigned long revolutionMicros =
          now - pulseTimes[slot];
        
        lastRevolutionMicros = revolutionMicros;

        float rpm =
          60000000.0 / revolutionMicros;

        if (!hasSmoothedRpm) {
          // Start at the first real measurement instead of slowly rising from zero.
          smoothedRpm = rpm;
          hasSmoothedRpm = true;
        } else {
          smoothedRpm =
            EMA_ALPHA * rpm +
            (1.0 - EMA_ALPHA) * smoothedRpm;
        }

        int midiValue = rpmToMidi(smoothedRpm);
        sendControllerValue(midiValue, smoothedRpm);  
      }

      pulseTimes[slot] = now;
      pulseCount++;
      lastPulseMicros = now;
    }
  }

  // Return the controller to zero after the spinner stops.
  if (
    lastPulseMicros != 0 &&
    now - lastPulseMicros > getStopTimeout()
  ) {
    sendControllerValue(0, 0.0);
    resetMotionTracking();
  }

  previousState = currentState;
}