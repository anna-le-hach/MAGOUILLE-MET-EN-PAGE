import sys,os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtTest import QTest
import magouille_mep.app as A
from magouille_mep import fonts
from magouille_mep.model import example_doc, MM
app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(A.QSS); fonts.load_builtin()
w=A.MainWindow(); w.resize(1500,900); w.show()
w.load_project({'doc':example_doc(),'assets':{}}); QApplication.processEvents(); w.zoom_fit(); QApplication.processEvents()
c=w.canvas; S=c.S(); R=w.renderer
def px(x,y): return QPoint(int(x*S),int(y*S))
p2=R.placements[1]
sid=[k for k,s in w.doc.d['stories'].items() if len(s['frames'])==2][0]
st=w.doc.d['stories'][sid]; f0=w.doc.item(st['frames'][0])
# double-clic dans le 4e paragraphe
bx,by=p2['x']+f0['x']+30,p2['y']+f0['y']+52
QTest.mouseDClick(c,Qt.LeftButton,Qt.NoModifier,px(bx,by)); QApplication.processEvents()
pt=w.page_text; print('page_text',pt is not None,'caret',pt.caret)
# placer le curseur au début du paragraphe 3 ("Tout ce qui ...")
pt.move((3,0),False)
QTest.keyClicks(c,'Bonjour ! ')
print('p3:',st['paras'][3]['h'][:40])
QTest.keyClick(c,Qt.Key_Backspace); QTest.keyClick(c,Qt.Key_Backspace)
print('p3 after bs:',st['paras'][3]['h'][:20])
# sélection mot + style de caractère
QTest.keyClick(c,Qt.Key_Left,Qt.ControlModifier|Qt.ShiftModifier)
print('sel',pt.sel(),repr(pt.selected_text()))
pt.set_char_style('accent'); print('p3 cs:',st['paras'][3]['h'][:60])
# entrée -> nouveau paragraphe, puis fusion
n0=len(st['paras']); pt.move((3,3),False); QTest.keyClick(c,Qt.Key_Return); print('paras',n0,'->',len(st['paras'])); QTest.keyClick(c,Qt.Key_Backspace); print('merged',len(st['paras']))
# flèches haut/bas + fin
pt.move((3,5),False); QTest.keyClick(c,Qt.Key_Down); print('down',pt.caret); QTest.keyClick(c,Qt.Key_End); print('end',pt.caret); QTest.keyClick(c,Qt.Key_Up); print('up',pt.caret)
# accents via méthode de saisie
from PySide6.QtGui import QInputMethodEvent
ev=QInputMethodEvent('',[]); ev.setCommitString('é'); QApplication.sendEvent(c,ev); print('ime',st['paras'][3]['h'][:50])
# clic-glisser pour sélectionner
QTest.mousePress(c,Qt.LeftButton,Qt.NoModifier,px(bx-20,by)); QTest.mouseMove(c,px(bx+20,by+8)); QTest.mouseRelease(c,Qt.LeftButton,Qt.NoModifier,px(bx+20,by+8))
print('drag sel',pt.sel(), repr(pt.selected_text()[:40]))
QTest.keyClick(c,Qt.Key_I,Qt.ControlModifier)
QApplication.processEvents(); w.grab().save('out/page1.png')
# annuler
for _ in range(3): w.undo()
print('after undo p3:', repr(w.doc.d['stories'][sid]['paras'][3]['h'][:90]))
QTest.keyClick(c,Qt.Key_Escape); print('ended',w.page_text is None)
# rotation : poignée
img=[i for i in w.doc.d['items'] if i['type']=='image'][0]; p3=R.pl(img['on']['p'])
w.select([img['id']]); hp=c.handle_pts(img)['rot']; cen=c.xf(img).map(QPointF(img['w']/2,img['h']/2))
QTest.mousePress(c,Qt.LeftButton,Qt.NoModifier,px(hp.x(),hp.y())); QTest.mouseMove(c,px(hp.x()+5,hp.y())); QTest.mouseMove(c,px(cen.x()+40,cen.y()-40)); QTest.mouseRelease(c,Qt.LeftButton,Qt.NoModifier,px(cen.x()+40,cen.y()-40))
print('rot',img.get('rot'), w.doc.item(img['id']).get('rot'))
# redimensionner un bloc tourné : coin bas droit
it=w.doc.item(img['id']); hp=c.handle_pts(it)[(1,1)]; ctr0=c.xf(it).map(QPointF(0,0))
QTest.mousePress(c,Qt.LeftButton,Qt.NoModifier,px(hp.x(),hp.y())); QTest.mouseMove(c,px(hp.x()+3,hp.y())); QTest.mouseMove(c,px(hp.x()+10,hp.y()+5)); QTest.mouseRelease(c,Qt.LeftButton,Qt.NoModifier,px(hp.x()+10,hp.y()+5))
it=w.doc.item(img['id']); ctr1=c.xf(it).map(QPointF(0,0)); print('resize rotated w,h',it['w'],it['h'],'anchor moved',round(ctr1.x()-ctr0.x(),2),round(ctr1.y()-ctr0.y(),2))
# rotation d'un texte
w.select([f0['id']]); w.set_prop('rot', -8)
QApplication.processEvents(); w.grab().save('out/page2.png')
from magouille_mep.pdfexport import export_pdf
export_pdf(w,'out/rot.pdf',2,3,True,False); print('pdf ok')
