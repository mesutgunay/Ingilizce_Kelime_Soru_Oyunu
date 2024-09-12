import sys
import requests
import random
from googletrans import Translator
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMessageBox, QInputDialog, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtGui import QIcon, QImage, QPixmap  # Burada gerekli sınıfları ekliyoruz
from PyQt5.QtCore import QTimer, Qt
from word_quiz_ui import Ui_WordQuizApp  # pyuic5 tarafından oluşturulan arayüz dosyası
import os

# Translator nesnesi oluştur
translator = Translator()

# Global değişkenler
correct_word = ""
translated_word = ""
options = []
setup_file = "setup.txt"
update_interval = 5 * 60  # Varsayılan 5 dakika
alarm_timer = None
tray_icon = None

# 4 adet rastgele İngilizce kelime üret
def get_random_words(num_words=4):
    url = f"https://random-word-api.herokuapp.com/word?number={num_words}"
    response = requests.get(url)
    word_list = response.json()
    return word_list

# Şıkları üret ve Türkçe çeviriyi seç
def create_quiz():
    words = get_random_words()
    global correct_word, translated_word, options
    correct_word = random.choice(words)
    translated_word = translator.translate(correct_word, src='en', dest='tr').text

    options = set(words)
    while len(options) < 4:
        num_question_marks = random.randint(3, 11)
        sp_param = '?' * num_question_marks
        url = f"https://api.datamuse.com/words?sp={sp_param}&md=f&max=10"
        response = requests.get(url)
        word_list = response.json()
        if word_list:
            for word in word_list:
                word = word['word']
                if word not in options and len(options) < 4:
                    options.add(word)
    
    options = list(options)
    random.shuffle(options)
    
    return translated_word, options, correct_word

# Ayarları setup.txt dosyasına kaydet
def save_settings():
    global update_interval
    with open(setup_file, 'w') as file:
        file.write(f"interval={update_interval // 60}\n")

# setup.txt dosyasından ayarları oku
def load_settings():
    global update_interval
    if os.path.exists(setup_file):
        with open(setup_file, 'r') as file:
            for line in file:
                if line.startswith("interval="):
                    try:
                        interval_minutes = int(line.split('=')[1].strip())
                        update_interval = interval_minutes * 60
                    except ValueError:
                        pass

# PyQt5 arayüz sınıfı
class WordQuizApp(QMainWindow, Ui_WordQuizApp):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.start_alarm_timer()  # Alarm zamanlayıcısını başlat
        self.load_initial_settings()  # Ayarları yükle ve gerekli işlemleri yap
        self.create_tray_icon()
        self.start_new_question()  # Uygulama başında hemen yeni bir soru başlat

        # Başlangıçta seçenek butonlarını gizle
        self.optionButton1.setVisible(False)
        self.optionButton2.setVisible(False)
        self.optionButton3.setVisible(False)
        self.optionButton4.setVisible(False)

        # Slotları bağlama
        self.optionButton1.clicked.connect(lambda: self.check_answer(self.optionButton1.text()))
        self.optionButton2.clicked.connect(lambda: self.check_answer(self.optionButton2.text()))
        self.optionButton3.clicked.connect(lambda: self.check_answer(self.optionButton3.text()))
        self.optionButton4.clicked.connect(lambda: self.check_answer(self.optionButton4.text()))
        self.passButton.clicked.connect(self.start_new_question)
        self.settingsButton.clicked.connect(self.open_settings)
        self.exitButton.clicked.connect(self.close)

    def load_initial_settings(self):
        load_settings()
        self.restart_alarm()  # Alarm zamanlayıcısını güncelle

    def start_new_question(self):
        self.show_loader()
        QTimer.singleShot(1500, self.update_question)  # 1.5 saniye sonra soruyu güncelle

    def update_question(self):
        global correct_word, translated_word, options
        translated_word, options, correct_word = create_quiz()
        self.questionLabel.setText(f"Türkçesi: {translated_word}")
        for i, button in enumerate([self.optionButton1, self.optionButton2, self.optionButton3, self.optionButton4]):
            button.setText(options[i])
            button.setVisible(True)  # Soru güncellendiğinde seçenekleri göster
        self.hide_loader()

    def show_loader(self):
        self.questionLabel.setText("Yeni soru üretiliyor...")
        self.optionButton1.setVisible(False)
        self.optionButton2.setVisible(False)
        self.optionButton3.setVisible(False)
        self.optionButton4.setVisible(False)

    def hide_loader(self):
        self.questionLabel.setText(f"Türkçesi: {translated_word}")
        self.optionButton1.setVisible(True)
        self.optionButton2.setVisible(True)
        self.optionButton3.setVisible(True)
        self.optionButton4.setVisible(True)

    def check_answer(self, selected_option):
        if selected_option == correct_word:
            QMessageBox.information(self, "Sonuç", "Doğru cevap!")
        else:
            QMessageBox.information(self, "Sonuç", f"Yanlış cevap. Doğru cevap: {correct_word}")
        
        reply = QMessageBox.question(self, "Devam et?", "Yeni soru sormak ister misiniz?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.start_new_question()
        else:
            self.minimize_to_tray()

    def minimize_to_tray(self):
        self.hide()
        tray_icon.show()


    def restore_from_tray(self, action):
        self.show()
        self.raise_()
        self.activateWindow()
        tray_icon.hide()
        self.start_new_question()

    def set_interval(self, minutes):
        global update_interval
        update_interval = minutes * 60
        self.restart_alarm()
        save_settings()  # Yeni ayarı dosyaya kaydet

    def start_alarm_timer(self):
        global alarm_timer
        if alarm_timer is None:
            alarm_timer = QTimer(self)  # alarm_timer'ı bu sınıfa bağlı olarak başlat
            alarm_timer.timeout.connect(self.show_alarm_message)

    def restart_alarm(self):
        global alarm_timer
        if alarm_timer is not None:
            if alarm_timer.isActive():
                alarm_timer.stop()
            if update_interval > 0:
                alarm_timer.start(update_interval * 1000)

    def show_alarm_message(self):
        self.show()  # Uygulamayı göster
        self.raise_()  # Uygulamayı ön plana getir
        self.activateWindow()  # Pencereyi etkinleştir
        self.start_new_question()  # Yeni soru başlat


    def open_settings(self):
        minutes, ok = QInputDialog.getInt(self, "Ayarlar", "Sorular arası dakika:", update_interval // 60, 1, 60)
        if ok:
            self.set_interval(minutes)

    def create_tray_icon(self):
        global tray_icon
        # Dinamik olarak oluşturulan bir icon kullanımı
        image = QImage(64, 64, QImage.Format_RGB888)
        image.fill(Qt.transparent)  # Şeffaf bir arka plan ile bir icon oluşturuluyor
        pixmap = QPixmap(image)
        tray_icon = QSystemTrayIcon(QIcon(pixmap), self)

        # Sağ tıklama menüsü oluşturuluyor
        tray_menu = QMenu()
        
        settings_action = QAction("Ayarlar", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)
        
        exit_action = QAction("Çıkış", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)
        
        # Menüyü tray icon'a bağlama
        tray_icon.setContextMenu(tray_menu)
        
        # Tray icon tıklandığında uygulamayı geri getir
        tray_icon.activated.connect(self.restore_from_tray)
        
        # Tray icon'u göster
        tray_icon.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = WordQuizApp()
    mainWin.show()
    sys.exit(app.exec_())
