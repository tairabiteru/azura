import wavelink

class Track(wavelink.Track):
    def __init__(self, track, **kwargs):
        super().__init__(track.id, track.info, track.query)
        self.ctx = kwargs['ctx']
        self.requester = kwargs['requester'] if 'requester' in kwargs else None
        self.start = kwargs['start'] if 'start' in kwargs else 0
        self.end = kwargs['end'] if 'end' in kwargs else -1

        self.start = self.start * 1000
        self.end = self.end * 1000 if self.end != -1 else -1
