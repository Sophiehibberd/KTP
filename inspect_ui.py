import inspect
from shiny.express import ui

print("nav_panel signature:", inspect.signature(ui.nav_panel))
print("navset_bar signature:", inspect.signature(ui.navset_bar))
print("ui members:", [n for n in dir(ui) if not n.startswith('_')])