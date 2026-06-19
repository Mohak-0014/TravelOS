"use client";

import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { ItineraryItemOut } from "@/lib/api";

// CSS dot marker avoids the broken default webpack/leaflet icon issue
const dotIcon = L.divIcon({
  className: "",
  html: '<div style="width:11px;height:11px;background:#60a5fa;border-radius:50%;border:2px solid rgba(255,255,255,0.9);box-shadow:0 0 8px rgba(59,130,246,0.8),0 1px 4px rgba(0,0,0,0.6)"></div>',
  iconSize: [11, 11],
  iconAnchor: [5, 5],
  popupAnchor: [0, -8],
});

interface Props {
  items: ItineraryItemOut[];
  centerLat: number;
  centerLng: number;
}

export default function TripMap({ items, centerLat, centerLng }: Props) {
  return (
    <MapContainer
      center={[centerLat, centerLng]}
      zoom={13}
      scrollWheelZoom={false}
      style={{ height: "220px", width: "100%", borderRadius: "0" }}
    >
      <TileLayer
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {items.map((item) =>
        item.latitude != null && item.longitude != null ? (
          <Marker
            key={item.id}
            position={[item.latitude, item.longitude]}
            icon={dotIcon}
          >
            <Popup>
              <span className="text-sm font-medium">{item.title}</span>
              {item.address && (
                <p className="text-xs text-gray-500 mt-0.5">{item.address}</p>
              )}
            </Popup>
          </Marker>
        ) : null,
      )}
    </MapContainer>
  );
}
