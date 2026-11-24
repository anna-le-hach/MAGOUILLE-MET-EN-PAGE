import sys,os,json
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtTest import QTest
import magouille_mep.app as A
from magouille_mep import fonts
from magouille_mep.model import example_doc
app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(A.QSS)
fonts.load_builtin()
w=A.MainWindow(); w.resize(1500,900); w.show()
w.load_project({'doc':example_doc(),'assets':{}})
QApplication.processEvents(); w.zoom_fit(); QApplication.processEvents()
w.grab().save('out/py1.png')
# select body frame on page 2 and open editor
st=[k for k,s in w.doc.d['stories'].items() if len(s['frames'])==2][0]
w.select([w.doc.d['stories'][st]['frames'][0]]); w.open_editor(st); QApplication.processEvents()
w.scroll_to_page(w.doc.d['pages'][1]['id']); QApplication.processEvents()
w.grab().save('out/py2.png')
print('over',w.doc.d['stories'][st].get('_over'))
from magouille_mep.pdfexport import export_pdf
export_pdf(w,'out/py.pdf',1,3,True,True)
w.tabs.setCurrentIndex(1); QApplication.processEvents(); w.grab().save('out/py3.png')
print('ok')
