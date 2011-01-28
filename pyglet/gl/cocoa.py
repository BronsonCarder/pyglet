#!/usr/bin/env python

'''
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id: $'

from pyglet.gl.base import Config, CanvasConfig, Context

from pyglet.libs.darwin import *
from pyglet.gl import ContextException
from pyglet.gl import gl
from pyglet.gl import agl

from pyglet.canvas.cocoa import CocoaCanvas


# Valid names for GL attributes and their corresponding NSOpenGL constant.
_gl_attributes = {
    'double_buffer': NSOpenGLPFADoubleBuffer,
    'stereo': NSOpenGLPFAStereo,
    'color_size': NSOpenGLPFAColorSize,            # replaces AGL_BUFFER_SIZE
    'sample_buffers': NSOpenGLPFASampleBuffers,
    'samples': NSOpenGLPFASamples,
    'aux_buffers': NSOpenGLPFAAuxBuffers,
    'alpha_size': NSOpenGLPFAAlphaSize,
    'depth_size': NSOpenGLPFADepthSize,
    'stencil_size': NSOpenGLPFAStencilSize,

    # Not exposed by pyglet API (set internally)
    'all_renderers': NSOpenGLPFAAllRenderers,
    'fullscreen': NSOpenGLPFAFullScreen,
    'minimum_policy': NSOpenGLPFAMinimumPolicy,
    'maximum_policy': NSOpenGLPFAMaximumPolicy,
    'screen_mask' : NSOpenGLPFAScreenMask,

    # Not supported in current pyglet API
    'color_float': NSOpenGLPFAColorFloat,
    'offscreen': NSOpenGLPFAOffScreen,
    'sample_alpha': NSOpenGLPFASampleAlpha,
    'multisample': NSOpenGLPFAMultisample,
    'supersample': NSOpenGLPFASupersample,
}

# NSOpenGL constants which do not require a value.
_boolean_gl_attributes = frozenset([
    NSOpenGLPFAAllRenderers, 
    NSOpenGLPFADoubleBuffer,
    NSOpenGLPFAStereo,
    NSOpenGLPFAMinimumPolicy,
    NSOpenGLPFAMaximumPolicy,
    NSOpenGLPFAOffScreen,
    NSOpenGLPFAFullScreen,
    NSOpenGLPFAColorFloat,
    NSOpenGLPFAMultisample,
    NSOpenGLPFASupersample,
    NSOpenGLPFASampleAlpha,
])


class CocoaConfig(Config):

    def match(self, canvas):
        # Construct array of attributes for NSOpenGLPixelFormat
        attrs = []
        for name, value in self.get_gl_attributes():
            attr = _gl_attributes.get(name)
            if not attr or not value:
                continue
            attrs.append(attr)
            if attr not in _boolean_gl_attributes:
                attrs.append(int(value))

        # Support for RAGE-II, which is not compliant.
        attrs.append(NSOpenGLPFAAllRenderers)

        # Force selection policy.
        attrs.append(NSOpenGLPFAMaximumPolicy)

        # NSOpenGLPFAFullScreen is always supplied so we can switch to and
        # from fullscreen without losing the context.  Also must supply the
        # NSOpenGLPFAScreenMask attribute with appropriate display ID.
        # Note that these attributes aren't necessary to render in fullscreen
        # on Mac OS X 10.6, because there we are simply rendering into a 
        # screen sized window.  See:
        # http://developer.apple.com/library/mac/#documentation/GraphicsImaging/Conceptual/OpenGL-MacProgGuide/opengl_fullscreen/opengl_cgl.html%23//apple_ref/doc/uid/TP40001987-CH210-SW6
        attrs.append(NSOpenGLPFAFullScreen)
        attrs.append(NSOpenGLPFAScreenMask)
        attrs.append(CGDisplayIDToOpenGLDisplayMask(CGMainDisplayID()))
        
        # Terminate the list.
        attrs.append(0)

        # Create the pixel format.
        pixel_format = NSOpenGLPixelFormat.alloc().initWithAttributes_(attrs)
                
        # Return the match list.
        if pixel_format is None:
            return []
        else:
            return [CocoaCanvasConfig(canvas, self, pixel_format)]


class CocoaCanvasConfig(CanvasConfig):

    def __init__(self, canvas, config, pixel_format):
        super(CocoaCanvasConfig, self).__init__(canvas, config)
        self._pixel_format = pixel_format

        # Query values for the attributes of the pixel format, and then set the
        # corresponding attributes of the canvas config.
        for name, attr in _gl_attributes.items():
            value = self._pixel_format.getValues_forAttribute_forVirtualScreen_(None, attr, 0)
            if value:
                setattr(self, name, value)

 
    def create_context(self, share):
        # Determine the shared NSOpenGLContext.
        if share:
            share_context = share._nscontext
        else:
            share_context = None

        # Create a new NSOpenGLContext.
        nscontext = NSOpenGLContext.alloc().initWithFormat_shareContext_(
            self._pixel_format,
            share_context)

        return CocoaContext(self, nscontext, share)

    def compatible(self, canvas):
        return isinstance(canvas, CocoaCanvas)


class CocoaContext(Context):

    def __init__(self, config, nscontext, share):
        super(CocoaContext, self).__init__(config, share)
        self.config = config
        self._nscontext = nscontext

    def attach(self, canvas):
        super(CocoaContext, self).attach(canvas)
        canvas.nsview.setPixelFormat_(self.config._pixel_format)
        canvas.nsview.setOpenGLContext_(self._nscontext)
        # The NSView instance should be attached to a nondeferred window before calling
        # setView, otherwise you get an "invalid drawable" message.
        self._nscontext.setView_(canvas.nsview)
        self.set_current()

    def detach(self):
        super(CocoaContext, self).detach()
        self._nscontext.clearDrawable()

    def set_current(self):
        self._nscontext.makeCurrentContext()
        super(CocoaContext, self).set_current()

    def update_geometry(self):
        # Need to call this method whenever the context drawable (an NSView)
        # changes size or location.
        self._nscontext.update()

    def set_full_screen(self):
        self._nscontext.setFullScreen()
        self._nscontext.makeCurrentContext()

    def destroy(self):
        super(CocoaContext, self).destroy()
        self._nscontext = None

    def set_vsync(self, vsync=True):
        # Does not work because of PyObjC bug.
        #self._nscontext.setValues_forParameter_([1], NSOpenGLCPSwapInterval)
        pass

    def get_vsync(self):
        value = self._nscontext.getValues_forParameter_(None, NSOpenGLCPSwapInterval)
        return value
        
    def flip(self):
        self._nscontext.flushBuffer()
