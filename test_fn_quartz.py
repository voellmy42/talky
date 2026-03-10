import Quartz
import time
import ApplicationServices

def on_event(proxy, type_, event, refcon):
    if type_ == Quartz.kCGEventFlagsChanged:
        flags = Quartz.CGEventGetFlags(event)
        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        
        # fn key code is 63
        if keycode == 63:
            pressed = (flags & Quartz.kCGEventFlagMaskSecondaryFn) != 0
            if pressed:
                print("fn pressed", flush=True)
            else:
                print("fn released", flush=True)
                # Exit for testing purposes
                Quartz.CFRunLoopStop(Quartz.CFRunLoopGetCurrent())
    return event

def listen_for_fn():
    try:
        trusted = ApplicationServices.AXIsProcessTrusted()
        print("Accessibility Trusted:", trusted)
    except Exception as e:
        print("Could not verify trust status natively.", e)
    
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
        on_event,
        None
    )
    if not tap:
        print("Failed to create event tap. Need Accessibility.")
        return
    
    runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        runLoopSource,
        Quartz.kCFRunLoopCommonModes
    )
    Quartz.CGEventTapEnable(tap, True)
    print("Listening for fn...", flush=True)
    Quartz.CFRunLoopRun()

if __name__ == "__main__":
    listen_for_fn()
