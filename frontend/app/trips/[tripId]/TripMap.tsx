"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { ItineraryItemOut } from "@/lib/api";

// Color-coded by item type
const PIN_COLORS: Record<string, string> = {
  activity: "#f87171",
  meal:     "#fbbf24",
  transport:"#34d399",
  lodging:  "#60a5fa",
  free:     "#fbbf24",
};

function makePin(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="width:11px;height:11px;background:${color};border-radius:50%;border:2.5px solid rgba(255,255,255,0.9);box-shadow:0 2px 8px rgba(0,0,0,0.5)"></div>`,
    iconSize: [11, 11],
    iconAnchor: [5.5, 5.5],
    popupAnchor: [0, -9],
  });
}

const hotelIcon = L.divIcon({
  className: "",
  html: '<div style="width:20px;height:20px;background:#f59e0b;border-radius:50%;border:2.5px solid rgba(255,255,255,0.95);box-shadow:0 2px 12px rgba(245,158,11,0.65);display:flex;align-items:center;justify-content:center;font-size:10px;line-height:1">🏨</div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -13],
});

interface HotelPin {
  lat: number;
  lng: number;
  name: string;
}

interface Props {
  items: ItineraryItemOut[];
  centerLat: number;
  centerLng: number;
  hotel?: HotelPin | null;
  height?: string;
}

// Auto-fits the map to show all pins
function FitBounds({ items, hotel }: { items: ItineraryItemOut[]; hotel: HotelPin | null | undefined }) {
  const map = useMap();

  useEffect(() => {
    const pts = items
      .filter((i) => i.latitude != null && i.longitude != null)
      .map((i) => L.latLng(i.latitude!, i.longitude!));

    if (hotel) pts.push(L.latLng(hotel.lat, hotel.lng));
    if (pts.length === 0) return;

    if (pts.length === 1) {
      map.setView(pts[0], 14, { animate: false });
    } else {
      map.fitBounds(L.latLngBounds(pts), { padding: [28, 28], maxZoom: 14, animate: false });
    }
  }, [map, items, hotel]);

  return null;
}

export default function TripMap({ items, centerLat, centerLng, hotel, height = "300px" }: Props) {
  return (
    <MapContainer
      center={[centerLat, centerLng]}
      zoom={13}
      scrollWheelZoom={false}
      zoomControl={false}
      style={{ height, width: "100%", borderRadius: 0 }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />

      <FitBounds items={items} hotel={hotel} />

      {items.map((item) =>
        item.latitude != null && item.longitude != null ? (
          <Marker
            key={item.id}
            position={[item.latitude, item.longitude]}
            icon={makePin(PIN_COLORS[item.item_type] ?? "#818cf8")}
          >
            <Popup>
              <div style={{ minWidth: 150 }}>
                <p style={{ fontSize: 12, fontWeight: 600, margin: 0, lineHeight: 1.4 }}>{item.title}</p>
                {item.start_time && (
                  <p style={{ fontSize: 10, color: "#94a3b8", marginTop: 3 }}>{item.start_time.slice(0, 5)}</p>
                )}
                {item.address && (
                  <p style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>{item.address}</p>
                )}
              </div>
            </Popup>
          </Marker>
        ) : null,
      )}

      {hotel && (
        <Marker position={[hotel.lat, hotel.lng]} icon={hotelIcon}>
          <Popup>
            <div style={{ minWidth: 150 }}>
              <p style={{ fontSize: 12, fontWeight: 700, margin: 0 }}>🏨 {hotel.name}</p>
              <p style={{ fontSize: 10, color: "#94a3b8", marginTop: 3 }}>Selected hotel</p>
            </div>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}
