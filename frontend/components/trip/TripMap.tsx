"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { ItineraryItemOut } from "@/lib/api";

// Brightened for the dark basemap — matches the budget donut / map legend colors.
const PIN_COLORS: Record<string, string> = {
  activity: "#D9A05B",
  meal: "#FFC46B",
  transport: "#3ECF8E",
  lodging: "#FF9E64",
  free: "#FFC46B",
};

function makePin(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="width:11px;height:11px;background:${color};border-radius:50%;border:2.5px solid #0B0F14;box-shadow:0 1px 4px rgba(0,0,0,0.6)"></div>`,
    iconSize: [11, 11],
    iconAnchor: [5.5, 5.5],
    popupAnchor: [0, -9],
  });
}

const hotelIcon = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;background:#FF9E64;border-radius:50%;border:3px solid #0B0F14;box-shadow:0 0 10px rgba(255,158,100,0.7)"></div>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
  popupAnchor: [0, -12],
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
    const pts = items.filter((i) => i.latitude != null && i.longitude != null).map((i) => L.latLng(i.latitude!, i.longitude!));

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
        url="https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png"
      />

      <FitBounds items={items} hotel={hotel} />

      {items.map((item) =>
        item.latitude != null && item.longitude != null ? (
          <Marker key={item.id} position={[item.latitude, item.longitude]} icon={makePin(PIN_COLORS[item.item_type] ?? "#7C807A")}>
            <Popup>
              <div style={{ minWidth: 150, fontFamily: "var(--font-instrument), sans-serif" }}>
                <p style={{ fontSize: 12, fontWeight: 600, margin: 0, lineHeight: 1.4, color: "#16181A" }}>{item.title}</p>
                {item.start_time && (
                  <p style={{ fontSize: 10, color: "#7C807A", marginTop: 3, fontFamily: "var(--font-spline-mono), monospace" }}>
                    {item.start_time.slice(0, 5)}
                  </p>
                )}
                {item.address && <p style={{ fontSize: 10, color: "#7C807A", marginTop: 2 }}>{item.address}</p>}
              </div>
            </Popup>
          </Marker>
        ) : null,
      )}

      {hotel && (
        <Marker position={[hotel.lat, hotel.lng]} icon={hotelIcon}>
          <Popup>
            <div style={{ minWidth: 150, fontFamily: "var(--font-instrument), sans-serif" }}>
              <p style={{ fontSize: 12, fontWeight: 700, margin: 0, color: "#16181A" }}>{hotel.name}</p>
              <p style={{ fontSize: 10, color: "#7C807A", marginTop: 3 }}>Selected hotel</p>
            </div>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}
