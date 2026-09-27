"""Local Tk lifecycle/state smoke check, no display hardware writes or global hooks."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from displayshift import DisplayShift
from shiftcore.config import DEFAULT_CONFIG
from shiftcore.engine import Result
from test_engine import FakeBackend

app = DisplayShift(copy.deepcopy(DEFAULT_CONFIG), FakeBackend(), start_services=False)
app.root.withdraw()
try:
    assert len(app.table.get_children()) == 3
    app.events.put(('scan', FakeBackend().displays))
    app.root.after_cancel(app.poll_id)
    app.consume_events()
    assert len(app.displays) == 3
    app.set_busy(True)
    assert 'disabled' in app.mac_button.state()
    assert not app.job('scan', lambda: [])  # prevent duplicate shortcut jobs
    app.events.put(('switch', [Result('ASUS VG27AQ3A', 'sent', '已发送'), Result('LG 27UP850N', 'failed', '待校准')]))
    app.root.after_cancel(app.poll_id)
    app.consume_events()
    assert not app.busy
    assert '未完成 1' in app.status.get()
    app.settings()
    assert app.dialog is not None
    app.dialog.update_idletasks()
    assert app.dialog.winfo_reqwidth() <= 1000
    app.dialog.destroy()
    app.dialog = None
    print('UI smoke passed: three profiles, scan, partial failure, duplicate guard, settings lifecycle')
finally:
    app.close()
