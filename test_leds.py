from gpiozero import LED
from time import sleep

led1 = LED(16)
led2= LED(26)

try:
    led1.on()
    led2.on()
    print("LED allumées")
    sleep(20)

    led1.off()
    led2.off()
    print("LED éteintes")

finally:
    led1.off()
    led2.off()