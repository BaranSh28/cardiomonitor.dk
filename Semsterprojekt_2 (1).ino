#include <SPI.h>
#include <TimerOne.h>

SPISettings settings(8000000, MSBFIRST, SPI_MODE0);
const long tSampleInMicros = 1000; // Ex. Sampling tid i mikrosekunder 

void setup() {
    Serial.begin(9600); // starter serial forbindelse
    SPI.begin();
    SPI.beginTransaction(settings);
    pinMode(10, OUTPUT);
    digitalWrite(10, HIGH);
    Timer1.initialize(tSampleInMicros);
    Timer1.attachInterrupt(measureAndSend);
}

void loop() {
    // Empty as everything happens in the timer interrupt
}

int getEKGADC() { // henter ADC værdi fra AD konverten og returnere det som integer. SPI overførsel for ADC værdi.
    digitalWrite(10, LOW);
    int adcValue = SPI.transfer16(0x00);
    digitalWrite(10, HIGH);
    return adcValue;
}

void measureAndSend() { //sender værdi via pc via serial forbindelse og returnere værdien. 
    int value = getEKGADC();
    Serial.println(value);
}