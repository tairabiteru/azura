import wavelink

class Track(wavelink.Track):
    def __init__(self, track, **kwargs):
        super().__init__(track.id, track.info, track.query)
        self.ctx = kwargs['ctx']
        self.requester = kwargs['requester'] if 'requester' in kwargs else None
