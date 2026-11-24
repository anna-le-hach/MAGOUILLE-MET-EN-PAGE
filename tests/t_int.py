import sys,os,json
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
import magouille_mep.app as A
from magouille_mep import fonts
from magouille_mep.model import new_doc
app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(A.QSS); fonts.load_builtin()
w=A.MainWindow(); w.resize(1500,900); w.show()
w.load_project({'doc':new_doc(pages=4),'assets':{}}); QApplication.processEvents(); w.zoom_fit(); QApplication.processEvents()
c=w.canvas; S=c.S()
def pt(pl,x,y): return QPoint(int((pl['x']+x)*S),int((pl['y']+y)*S))
p1=w.renderer.placements[0]
# outil texte : tracé
w.set_tool('text')
QTest.mousePress(c,Qt.LeftButton,Qt.NoModifier,pt(p1,20,20)); QTest.mouseMove(c,pt(p1,60,50)); QTest.mouseMove(c,pt(p1,110,90)); QTest.mouseRelease(c,Qt.LeftButton,Qt.NoModifier,pt(p1,110,90))
QApplication.processEvents()
print('page_text',w.page_text is not None, len(w.doc.d['items']))
QTest.keyClicks(c,'Un titre'); w.page_text.set_para_style('titre')
QTest.keyClick(c,Qt.Key_Return); w.page_text.set_para_style('corps')
QTest.keyClicks(c,'Du texte en '); QTest.keyClick(c,Qt.Key_B,Qt.ControlModifier); QTest.keyClicks(c,'gras'); QTest.keyClick(c,Qt.Key_B,Qt.ControlModifier); QTest.keyClicks(c,' et normal.')
from magouille_mep.model import FAUX_TEXTE
w.page_text.insert("\n"+"\n".join(FAUX_TEXTE*2))
QTest.keyClick(c,Qt.Key_Escape); QApplication.processEvents()
sid=[k for k,s in w.doc.d['stories'].items() if 'p' in w.doc.item(s['frames'][0])['on']][0]
st=w.doc.d['stories'][sid]
print('paras',[ (p['s'],p['h'][:40]) for p in st['paras'][:3]], 'over',st.get('_over'))
# chaînage vers page 2 (clic dans le vide)
it=w.doc.item(st['frames'][0]); w.select([it['id']])
b=c.ports(it)['out']; k=S/ (72/25.4)
QTest.mouseClick(c,Qt.LeftButton,Qt.NoModifier,QPoint(int(b.center().x()*k),int(b.center().y()*k)))
print('linking',w.link_from is not None)
p2=w.renderer.placements[1]
QTest.mouseClick(c,Qt.LeftButton,Qt.NoModifier,pt(p2,20,20)); QApplication.processEvents()
print('frames',len(st['frames']),'over',st.get('_over'))
# déplacer le bloc
it2=w.doc.item(st['frames'][1]); x0=it2['x']
QTest.mousePress(c,Qt.LeftButton,Qt.NoModifier,pt(p2,40,40)); QTest.mouseMove(c,pt(p2,45,45)); QTest.mouseMove(c,pt(p2,52,47)); QTest.mouseRelease(c,Qt.LeftButton,Qt.NoModifier,pt(p2,52,47))
print('moved',x0,'->',w.doc.item(it2['id'])['x'])
w.undo(); print('undo ->',w.doc.item(it2['id'])['x']); w.redo()
# image dépôt
w.drop_file('out/photo.jpg', p2['x']+70, p2['y']+150, None)
print('items',len(w.doc.d['items']),'assets',len(w.doc.assets),'ppi',w.eff_ppi(w.doc.item(w.sel[0])))
# rectangle
w.set_tool('rect'); QTest.mousePress(c,Qt.LeftButton,Qt.NoModifier,pt(p1,10,150)); QTest.mouseMove(c,pt(p1,40,170)); QTest.mouseMove(c,pt(p1,60,180)); QTest.mouseRelease(c,Qt.LeftButton,Qt.NoModifier,pt(p1,60,180))
# style
w.tabs.setCurrentIndex(1); w.styles.cur='corps'; w.styles.set('size',13); print('over after 13pt',st.get('_over'))
# gabarit
w.enter_master('A'); QApplication.processEvents(); w.grab().save('out/pyM.png'); w.exit_master()
# save + reload
w.path='out/projpy.json'; w.save()
w.load_file('out/projpy.json'); print('reloaded items',len(w.doc.d['items']),len(w.doc.assets))
# web project compat
w.load_file('out/proj.json'); print('web proj items',len(w.doc.d['items']))
QApplication.processEvents(); w.grab().save('out/pyW.png')
w.load_file('out/projpy.json'); QApplication.processEvents(); w.select([]); w.tabs.setCurrentIndex(3); QApplication.processEvents()
w.scroll_to_page(w.doc.d['pages'][0]['id']); QApplication.processEvents()
w.grab().save('out/pyI.png')
from magouille_mep.pdfexport import export_pdf
export_pdf(w,'out/py2.pdf',1,2,True,False); print('pdf ok')
