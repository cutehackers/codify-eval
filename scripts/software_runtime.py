"""External GTK/AT-SPI automation for real Flutter Linux executables.

Import inside the pinned Linux image. No Dart application internals are inspected.
"""
import os
import pathlib
import subprocess
import time

class GuiDriver:
    def __init__(self, timeout=8):
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi, Gio, GLib
        self.Atspi=Atspi
        self.timeout=timeout
        self.events=[]
        self.process=None
        self.log=None
        bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        for name in ('IsEnabled','ScreenReaderEnabled'):
            bus.call_sync('org.a11y.Bus','/org/a11y/bus','org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.a11y.Status',name,GLib.Variant('b',True))),None,Gio.DBusCallFlags.NONE,-1,None)

    def launch(self, executable, data_dir, log_path, environment=None):
        if self.process is not None:raise RuntimeError('stop previous process before launch')
        pathlib.Path(log_path).parent.mkdir(parents=True,exist_ok=True)
        self.log=open(log_path,'w')
        self.process=subprocess.Popen([str(executable)],stdout=self.log,stderr=subprocess.STDOUT,env={**os.environ,'EVAL_DATA_DIR':str(data_dir),'GTK_MODULES':'atk-bridge','ACCESSIBILITY_ENABLED':'1',**(environment or {})})
        self.events.append({'action':'launch','pid':self.process.pid,'executable':str(executable),'data_dir':str(data_dir)})
        return self.process.pid

    def stop(self):
        if self.process is None:return
        pid=self.process.pid
        self.process.terminate()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        self.events.append({'action':'stop','pid':pid,'returncode':self.process.returncode})
        self.process=None
        self.log.close();self.log=None
        time.sleep(0.25)

    def nodes(self):
        def walk(node):
            try:
                yield node
                for i in range(node.get_child_count()):
                    child=node.get_child_at_index(i)
                    if child is not None:yield from walk(child)
            except Exception:return
        return list(walk(self.Atspi.get_desktop(0)))

    def snapshot(self):
        result=[]
        for node in self.nodes():
            try:
                name=node.get_name()
                if name:result.append({'name':name,'role':node.get_role_name(),'interfaces':list(node.get_interfaces())})
            except Exception:pass
        return result

    def find(self,label,exact=True,interface=None):
        deadline=time.monotonic()+self.timeout
        while time.monotonic()<deadline:
            for node in self.nodes():
                try:
                    match=node.get_name()==label if exact else label in node.get_name()
                    if match and (interface is None or interface in node.get_interfaces()):return node
                except Exception:pass
            if self.process is not None and self.process.poll() is not None:raise AssertionError('application exited: '+str(self.process.returncode))
            time.sleep(0.1)
        raise AssertionError(f'accessible product label missing: {label!r}; tree={self.snapshot()}')

    def can_click(self,label):
        for node in self.nodes():
            try:
                if node.get_name()!=label or 'Action' not in node.get_interfaces():continue
                action=node.get_action_iface()
                if any(action.get_action_name(i).lower() in ('tap','click','press','activate') for i in range(action.get_n_actions())):return True
            except Exception:pass
        return False

    def click(self,label):
        deadline=time.monotonic()+self.timeout
        last_actions=[]
        while time.monotonic()<deadline:
            for node in self.nodes():
                try:
                    if node.get_name()!=label or 'Action' not in node.get_interfaces():continue
                    action=node.get_action_iface()
                    actions=[action.get_action_name(i).lower() for i in range(action.get_n_actions())]
                    last_actions=actions
                    index=next((i for i,name in enumerate(actions) if name in ('tap','click','press','activate')),None)
                    if index is not None and action.do_action(index):
                        self.events.append({'action':'click','label':label})
                        time.sleep(0.2);return
                except Exception:continue
            time.sleep(0.1)
        raise AssertionError(f'no enabled click action for {label!r}: {last_actions}; tree={self.snapshot()}')

    def enter(self,label,value):
        deadline=time.monotonic()+self.timeout
        while time.monotonic()<deadline:
            for node in self.nodes():
                try:
                    if node.get_name()!=label or 'EditableText' not in node.get_interfaces():continue
                    action=node.get_action_iface()
                    focus=next((i for i in range(action.get_n_actions()) if action.get_action_name(i).lower()=='focus'),None)
                    focused=action.do_action(focus) if focus is not None else node.get_component_iface().grab_focus()
                    if not focused:continue
                    time.sleep(0.2)
                    if node.get_editable_text_iface().set_text_contents(value):
                        self.events.append({'action':'enter','label':label,'value':value})
                        time.sleep(0.2);return
                except Exception:continue
            time.sleep(0.1)
        raise AssertionError('no enabled editable field action: '+label)

    def present(self,label,exact=True):
        self.find(label,exact=exact)
        self.events.append({'action':'assert_present','label':label,'exact':exact})

    def absent(self,label,exact=True):
        time.sleep(0.2)
        for node in self.nodes():
            try:
                name=node.get_name()
                if (name==label if exact else label in name):raise AssertionError(f'forbidden product label present: {label!r}')
            except AssertionError:raise
            except Exception:pass
        self.events.append({'action':'assert_absent','label':label,'exact':exact})

    def count(self,prefix):
        return sum(1 for node in self.nodes() if node.get_name().startswith(prefix))
