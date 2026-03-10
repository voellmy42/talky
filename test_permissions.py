import AppKit
import Quartz

options = {AppKit.kAXTrustedCheckOptionPrompt.encode('utf-8'): True}
trusted = AppKit.AXIsProcessTrustedWithOptions(options)
print("Accessibility Trusted:", trusted)
