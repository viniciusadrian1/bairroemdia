"""Presentation for server-classified sources, also used by persisted reports."""
SOURCE_LABELS = {'furadeira': 'Furadeira', 'obra_ferramentas': 'Obra / ferramentas',
                 'musica': 'Música', 'outro': 'Outro tipo de som',
                 'incerto': 'Tipo de som inconclusivo'}


def neighborhood_source(event):
    source = (event.get('analysis') or {}).get('neighborhood_source')
    return source if isinstance(source, dict) and source.get('label') in SOURCE_LABELS else None
