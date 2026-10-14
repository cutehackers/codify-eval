import os, subprocess, time, json
import gi
gi.require_version('Atspi','2.0')
from gi.repository import Atspi, Gio, GLib
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
for name in ['IsEnabled','ScreenReaderEnabled']:
 try:bus.call_sync('org.a11y.Bus','/org/a11y/bus','org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.a11y.Status',name,GLib.Variant('b',True))),None,Gio.DBusCallFlags.NONE,-1,None)
 except Exception as e:print('enable:',str(e),flush=True)
process=subprocess.Popen(['/work/repo/build/linux/arm64/release/bundle/notes_app'],env={**os.environ,'EVAL_DATA_DIR':'/tmp/probe-notes','GTK_MODULES':'atk-bridge','ACCESSIBILITY_ENABLED':'1'})
time.sleep(4)
def tree(node,depth=0):
 try:
  print(' '*depth,node.get_role_name(),repr(node.get_name()),'interfaces',node.get_interfaces(),flush=True)
  for i in range(node.get_child_count()):tree(node.get_child_at_index(i),depth+1)
 except Exception as e:print('tree error',e)
root=Atspi.get_desktop(0)
def walk(node):
 yield node
 for i in range(node.get_child_count()):yield from walk(node.get_child_at_index(i))
button=next(n for n in walk(root) if n.get_name()=='새 메모')
action=button.get_action_iface();print('actions',[(i,action.get_action_name(i)) for i in range(action.get_n_actions())],flush=True);action.do_action(0);time.sleep(2)
tree(Atspi.get_desktop(0));process.terminate();process.wait(timeout=5)
