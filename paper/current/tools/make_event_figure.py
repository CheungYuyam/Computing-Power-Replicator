"""Render user-selected Figure 7 C layout from the frozen event records."""
import design_figure7_options as d

def render():
    previous = d.OUT
    d.OUT = d.ROOT / 'figures/systems'
    try:
        d.zoomed('fig_same_stream_events')
    finally:
        d.OUT = previous

if __name__ == '__main__':
    render()
