import speech_recognition as sr

#initialize speech recognizer
r = sr.Recognizer()

def record():
    while True:
        try:
            #designate microphone as input
            with sr.Microphone() as source:
                #prepare recognizer to recieve input
                r.adjust_for_ambient_noise(source, duration=0.2)
                #listen for speech
                audio = r.listen(source)
                #recognize and store speech
                speech  = r.recognize_google(audio)
                return speech

        #error handling
        except sr.RequestError as e:
            print("could not request results; {0}".format(e))
        
        except sr.UnknownValueError:
            print("error occured")


while True:
    text = record()
    print(text)
    print("finished...")