import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from rangelab import RangeLab, configure
from engine import ROOT

app = QApplication([])
configure(app)
window = RangeLab()
window.timer.stop()
window.show()
app.processEvents()
window.grab().save(str(ROOT/'assets/preview.png'))
window.navigate('Aim & firing')
app.processEvents()
window.grab().save(str(ROOT/'assets/preview-aim.png'))
window.navigate('Visibility')
app.processEvents()
window.grab().save(str(ROOT/'assets/preview-visibility.png'))
window.navigate('Configuration')
app.processEvents()
window.grab().save(str(ROOT/'assets/preview-configuration.png'))
icon = QIcon(str(ROOT/'assets/rangelab.svg'))
icon.pixmap(256, 256).save(str(ROOT/'assets/rangelab.ico'))
window.close()
