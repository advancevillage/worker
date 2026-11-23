#!/usr/bin/env python3
"""Exact integer checks for disjoint page regions, independently per view."""
import argparse
import json
from pathlib import Path
from extract_content import cross, intersects, polygon_points


def inside(point, polygon):
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > point[1]) != (b[1] > point[1]):
            if (cross(a, b, point) > 0) == (b[1] > a[1]):
                result = not result
    return result


def bounds(points):
    return min(x for x,y in points), min(y for x,y in points), max(x for x,y in points), max(y for x,y in points)


def overlap_boxes(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def conflicts(polygons):
    """Yield region pairs with crossing/touching edges or complete containment."""
    boxes = [bounds(p) for p in polygons]
    edges = [list(zip(p, p[1:] + p[:1])) for p in polygons]
    edge_boxes = [[bounds([a,b]) for a,b in es] for es in edges]
    active = []
    for j in sorted(range(len(polygons)), key=lambda i: boxes[i][0]):
        active = [i for i in active if boxes[i][2] >= boxes[j][0]]
        for i in active:
            if not overlap_boxes(boxes[i], boxes[j]):
                continue
            evidence = None
            for ei, (a,b) in enumerate(edges[i]):
                for ej, (c,d) in enumerate(edges[j]):
                    if overlap_boxes(edge_boxes[i][ei], edge_boxes[j][ej]) and intersects(a,b,c,d):
                        evidence = {'kind': 'boundary_intersection', 'edges': [ei,ej], 'segments': [[a,b],[c,d]]}
                        break
                if evidence:
                    break
            if evidence is None:
                if inside(polygons[i][0], polygons[j]):
                    evidence = {'kind':'containment', 'contained':i, 'point':polygons[i][0]}
                elif inside(polygons[j][0], polygons[i]):
                    evidence = {'kind':'containment', 'contained':j, 'point':polygons[j][0]}
            if evidence:
                yield {'regions': [i,j], **evidence}
        active.append(j)


def require_disjoint(polygons, view):
    problem = next(conflicts(polygons), None)
    if problem:
        raise ValueError(f'{view}: region conflict (zero-based indices): {json.dumps(problem, ensure_ascii=False)}')


def audit(page):
    results = []
    for view in ('areas', 'trans'):
        if view not in page:
            continue
        points = [polygon_points(a['polygon'], page['width'], page['height']) for a in page[view]]
        results.extend({'view':view, **p} for p in conflicts(points))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    page = json.loads(args.page.read_text())
    issues = audit(page)
    report = {'pid':page.get('pid'), 'passed':not issues, 'conflicts':issues}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(f'{len(issues)} conflicts; report: {args.output}')
    return 1 if issues else 0

if __name__ == '__main__':
    raise SystemExit(main())
