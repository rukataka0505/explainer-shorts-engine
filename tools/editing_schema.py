"""JSON Schema for the existing project.json editing field, derived from the registry."""
from common import REPO_ROOT, write_json
from editing import REGISTRY


def obj(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


def numeric(limits, integer=False):
    default, lo, hi = limits
    return {'type': 'integer' if integer else 'number', 'default': default, 'minimum': lo, 'maximum': hi}


def schema():
    string = {'type': 'string', 'minLength': 1}
    unit = {'type': 'number', 'minimum': 0, 'maximum': 1}
    positive = {'type': 'number', 'minimum': 0}
    coordinate = obj({'x': unit, 'y': unit}, ('x', 'y'))
    target = {'shot': string, 'line': string, 'keyword': string, 'anchor': coordinate, 'point': coordinate}
    time_base = {'edge': {'enum': ['start', 'end']}, 'offset': {'type': 'number'}}
    definitions = {
        'time': {'oneOf': [positive, obj({'line': string, 'word': string, **time_base}, ('line',)), obj({'shot': string, **time_base}, ('shot',))]},
        'audio': obj({'sfx': string, 'sync': {'enum': ['start', 'peak_velocity', 'impact', 'landing', 'end']},
                      'offset_ms': numeric([0, -1000, 1000]), 'volume': numeric([.3, 0, 2])}, ('sfx',)),
        'sound': obj({'path': string, 'source_start': positive, 'duration': {'type': 'number', 'exclusiveMinimum': 0},
                      'marker': positive, 'volume': numeric([.3, 0, 2])}, ('path',)),
        'layer': obj({'path': string, 'depth': numeric([1, .1, 2])}, ('path',)),
        'media': obj({'path': string, 'source_start': positive, 'speed': {'type': 'number', 'exclusiveMinimum': 0},
                      'fit': {'enum': ['cover', 'contain']}, 'camera': {'type': 'array', 'minItems': 1, 'items':
                          obj({'at': unit, 'x': unit, 'y': unit, 'zoom': {'type': 'number', 'minimum': 1}})}}, ('path',)),
    }
    params = {name: obj({key: numeric(limits, key == 'slices') for key, limits in spec['params'].items()})
              for name, spec in REGISTRY['effects'].items()}
    variants = []
    for family, entries in (('effect', REGISTRY['effects']), ('pattern', REGISTRY['patterns'])):
        for name in entries:
            names = [name] if family == 'effect' else entries[name]
            properties = {
                'id': {'type': 'string', 'pattern': '^[A-Za-z0-9_-]+$'}, 'version': {'const': 1, 'default': 1},
                family: {'const': name}, 'reason': string, 'intent': {'type': 'string'}, 'emotion': {'type': 'string'},
                'importance': unit, 'intensity': numeric([.5, 0, 1]), 'seed': {'type': 'string'}, 'variation': numeric([0, 0, 1]),
                'at': {'$ref': '#/$defs/time'}, 'audio': {'$ref': '#/$defs/audio'},
                'params': params[name] if family == 'effect' else obj({n: params[n] for n in names})}
            needs = set()
            required = ['id', family, 'reason', 'target']
            for n in names:
                spec = REGISTRY['effects'][n]
                needs.add('line' if spec['stage'] in ('caption', 'speech') else 'shot')
                if n == 'keyword_highlight':
                    needs.add('keyword')
                if n == 'callout':
                    needs.add('point')
                    properties['label'] = {'type': 'string', 'minLength': 1, 'maxLength': 20}
                    required.append('label')
                if n == 'broll_cutaway':
                    properties['media'] = {'$ref': '#/$defs/media'}
                    required.append('media')
                if spec['stage'] == 'layers':
                    properties['layers'] = {'type': 'array', 'minItems': 1, 'items': {'$ref': '#/$defs/layer'}}
                    required.append('layers')
                if n == 'whip_transition':
                    properties['direction'] = {'enum': ['left', 'right'], 'default': 'left'}
            properties['target'] = obj(target, sorted(needs))
            if family == 'effect' and name != 'jump_cut_tighten':
                properties['duration'] = numeric(REGISTRY['effects'][name]['duration'])
            if name == 'jump_cut_tighten':
                properties.pop('at')
                properties.pop('audio')
            key = f'{family}_{name}'
            definitions[key] = obj(properties, required)
            variants.append({'$ref': '#/$defs/' + key})
    policy = obj({
        'strong_effect_cooldown': numeric([2, 0, 30]),
        'max_per_10s': obj({name: {'type': 'integer', 'minimum': 0, 'maximum': 100} for name in REGISTRY['effects']}),
        'never_stack': {'type': 'array', 'items': {'type': 'array', 'minItems': 2, 'items': {'enum': list(REGISTRY['effects'])}}}})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': 'Shorts project.json editing v1',
            '$defs': definitions, **obj({'version': {'const': 1, 'default': 1}, 'seed': {'type': 'string'},
                'renderer': {'enum': ['cpu', 'webgl'], 'default': 'cpu'},
                'caption_animation': {'enum': ['none', 'caption_pop'], 'default': 'none'},
                'events': {'type': 'array', 'items': {'oneOf': variants}}, 'policy': policy,
                'sounds': {'type': 'object', 'additionalProperties': {'$ref': '#/$defs/sound'}}})}


if __name__ == '__main__':
    write_json(REPO_ROOT / 'editing/schema.v1.json', schema())
