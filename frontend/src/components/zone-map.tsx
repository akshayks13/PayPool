"use client";

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";

export function ZoneMap({
  coordinates,
  onChange,
}: {
  coordinates: [number, number][];
  onChange: (points: [number, number][]) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const layer = useRef<Leaflet.LayerGroup | null>(null);
  const current = useRef(coordinates);
  const change = useRef(onChange);
  const [library, setLibrary] = useState<typeof Leaflet | null>(null);
  const [tilesUnavailable, setTilesUnavailable] = useState(false);
  current.current = coordinates;
  change.current = onChange;
  useEffect(() => {
    let disposed = false;
    import("leaflet").then((L) => {
      if (disposed || !element.current) return;
      const instance = L.map(element.current, {
        scrollWheelZoom: false,
      }).setView([12.97, 77.6], 11);
      map.current = instance;
      layer.current = L.layerGroup().addTo(instance);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19,
      })
        .on("tileerror", () => setTilesUnavailable(true))
        .addTo(instance);
      instance.on("click", (e) =>
        change.current([
          ...current.current,
          [Number(e.latlng.lng.toFixed(6)), Number(e.latlng.lat.toFixed(6))],
        ]),
      );
      if (current.current.length >= 3)
        instance.fitBounds(
          L.latLngBounds(current.current.map(([lon, lat]) => [lat, lon])),
          { padding: [25, 25] },
        );
      setLibrary(L);
    });
    return () => {
      disposed = true;
      map.current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (!library || !layer.current) return;
    layer.current.clearLayers();
    if (coordinates.length >= 3)
      library
        .polygon(
          coordinates.map(([lon, lat]) => [lat, lon]),
          { color: "#2563eb" },
        )
        .addTo(layer.current);
    coordinates.forEach(([lon, lat], index) => {
      const marker = library
        .marker([lat, lon], {
          draggable: true,
          icon: library.divIcon({
            className: "",
            html: `<span style="display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#1d4ed8;color:white;font-weight:bold">${index + 1}</span>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          }),
        })
        .addTo(layer.current!);
      marker.on("dragend", () => {
        const p = marker.getLatLng();
        const points = [...current.current];
        points[index] = [Number(p.lng.toFixed(6)), Number(p.lat.toFixed(6))];
        change.current(points);
      });
    });
  }, [coordinates, library]);
  return (
    <div className="space-y-2">
      <div
        ref={element}
        aria-label="Delivery boundary map; click to add a vertex"
        className="relative z-0 h-80 w-full rounded-xl border bg-slate-100"
      />
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>Click to add boundary points. Drag numbered points to edit.</span>
        <button
          type="button"
          className="font-semibold text-blue-700"
          onClick={() => onChange(coordinates.slice(0, -1))}
        >
          Undo point
        </button>
        <button
          type="button"
          className="font-semibold text-red-700"
          onClick={() => onChange([])}
        >
          Reset boundary
        </button>
      </div>
      {tilesUnavailable && (
        <p className="text-xs text-amber-800">
          Map tiles are unavailable. Boundary coordinates remain editable below.
        </p>
      )}
    </div>
  );
}
