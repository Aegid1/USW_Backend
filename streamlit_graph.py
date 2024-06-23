import streamlit as st
import matplotlib.pyplot as plt

# Textabschnitte und ihre Stimmungen
sections = [
    "Der Internationale Gerichtshof prüft die Rechtmäßigkeit der israelischen Besatzungspolitik in den palästinensischen Gebieten.",
    "Während Palästinenser Apartheid und Kolonialismus anprangern, weist Israel die Vorwürfe zurück und betont das Recht auf Selbstverteidigung.",
    "Trotz vergangener Friedensbemühungen herrscht seit 2014 Stillstand in den Verhandlungen.",
    "Die Anhörungen sollen klären, ob Israels Besatzungspolitik Völkerrecht verletzt.",
    "Israel und Deutschland boykottieren das Verfahren.",
    "Palästinenser fordern einen unabhängigen Staat mit Ost-Jerusalem als Hauptstadt.",
    "Das Gutachten des IGH könnte internationalen Druck auf Israel erhöhen und die Zwei-Staaten-Lösung beeinflussen."
]

# Stimmung (1 = positiv, 0 = neutral, -1 = negativ)
sentiments = [0, -1, -1, 0, -1, 0.5, 0.5]

# Erstellen des Graphen
plt.figure(figsize=(10, 6))
plt.barh(range(len(sections)), sentiments, color=['blue' if s > 0 else 'red' if s < 0 else 'gray' for s in sentiments])
plt.yticks(range(len(sections)), sections)
plt.xlabel('Stimmung')
plt.title('Stimmung des Artikels')
plt.grid(True)

# Streamlit-Ausgabe
st.pyplot(plt)