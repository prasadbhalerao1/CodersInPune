"use client";

import { FilmLayer, filmsOn, useMotionAllowed } from "../film-layer";
import { balloon } from "./balloon";
import { dominoes } from "./dominoes";
import { lights } from "./lights";
import { pixar } from "./pixar";
import { plane } from "./plane";

const SCRIPTS = [pixar, dominoes, balloon, plane, lights];

/** The idle films (besides the lasso, which hosts itself). One plays at a time, only when still. */
export function Films() {
  const allowed = useMotionAllowed();
  if (!filmsOn || !allowed) return null;
  return (
    <>
      {SCRIPTS.map((s) => (
        <FilmLayer key={s.name} script={s} />
      ))}
    </>
  );
}
