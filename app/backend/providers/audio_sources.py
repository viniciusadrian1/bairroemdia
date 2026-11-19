"""Additive neighborhood-source policy; independent of temporal accessibility events.

Uses clip means from the unchanged, pinned YAMNet. No loudness measurement,
legal assessment, retraining, or local calibration. Never rewrites old events.
"""

SOURCE_PROFILE_VERSION = 'neighborhood-v1'
CONSTRUCTION = {'Drill', 'Hammer', 'Jackhammer', 'Sawing', 'Sanding', 'Power tool', 'Tools'}
MIN_SOURCE_SCORE = .35
SOURCE_MARGIN = .05


def classify_source(labels, scores):
    # The pinned official vocabulary groups Music and its children at 132..276.
    # Use names as boundaries so explicit synthetic fixtures can omit this subtree.
    music = {'Music'}
    if 'Music' in labels and 'Scary music' in labels:
        music.update(labels[labels.index('Music'):labels.index('Scary music') + 1])

    def family(name):
        if name in CONSTRUCTION:
            return 'obra_ferramentas'
        if name in music:
            return 'musica'
        return 'outro'

    top = max(range(len(scores)), key=scores.__getitem__)
    name, score = labels[top], float(scores[top])
    group = family(name)
    competing = max((s for label, s in zip(labels, scores) if family(label) != group), default=0.)
    reason = 'Fonte sugerida pela maior média de classe no clipe; requer conferência do morador.'
    result = 'furadeira' if name == 'Drill' else group
    if score < MIN_SOURCE_SCORE:
        result, reason = 'incerto', 'Escores baixos: descreva o que ouviu e confira a gravação.'
    elif group != 'outro' and score - competing < SOURCE_MARGIN:
        result, reason = 'incerto', 'Tipos de som concorrentes: a gravação não sustenta uma única sugestão.'
    elif group == 'outro':
        reason = 'A classe predominante não corresponde a furadeira, ferramentas de obra ou música.'
    return {'label': result, 'score': score, 'model_class': name,
            'version': SOURCE_PROFILE_VERSION, 'aggregation': 'clip_mean', 'reason': reason}
