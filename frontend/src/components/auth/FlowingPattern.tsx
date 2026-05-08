"use client";
import React, { useEffect, useRef } from "react";

interface FlowingPatternProps {
  isDarkMode?: boolean;
}

export default function FlowingPattern({ isDarkMode = true }: FlowingPatternProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    interface Pill {
      x: number;
      y: number;
      width: number;
      length: number;
      speed: number;
      color: string;
      isLight: boolean;
    }

    let pills: Pill[] = [];
    const colWidth = 36;

    const getColors = () => {
      // HACKBRICKS-inspired pastel/light colors
      return {
        blue: "rgba(191, 219, 254, 0.6)", // #bfdbfe
        purple: "rgba(233, 213, 255, 0.6)", // #e9d5ff
        pink: "rgba(251, 207, 232, 0.6)", // #fbcfe8
        white: "rgba(255, 255, 255, 0.8)"
      };
    };

    const colors = getColors();

    const initPills = () => {
      pills = [];
      const columns = Math.ceil(width / colWidth);

      for (let column = 0; column < columns; column++) {
        const numPills = 3 + Math.random() * 5;
        for (let index = 0; index < numPills; index++) {
          const rand = Math.random();
          let color = colors.blue;
          if (rand > 0.7) color = colors.purple;
          else if (rand > 0.4) color = colors.pink;
          else if (rand > 0.2) color = colors.white;

          pills.push({
            x: column * colWidth + colWidth / 2,
            y: Math.random() * height * 2 - height,
            width: colWidth * (0.3 + Math.random() * 0.4),
            length: 60 + Math.random() * 180,
            speed: 0.2 + Math.random() * 0.5,
            color,
            isLight: rand > 0.2
          });
        }
      }
    };

    initPills();

    let animationId: number;

    const render = () => {
      // Clear the canvas each frame
      context.clearRect(0, 0, width, height);

      // We remove the solid fillRect to allow the AuthBackdrop radial gradients to show through
      // If the user wants a solid white background, we can re-enable this.

      pills.forEach((pill) => {
        pill.y += pill.speed;
        if (pill.y > height + 150) {
          pill.y = -pill.length - Math.random() * 100;
        }

        context.beginPath();
        context.lineCap = "round";
        context.lineWidth = pill.width;
        
        // Soften shadows for light mode
        context.shadowBlur = 0; 
        context.strokeStyle = pill.color;
        context.moveTo(pill.x, pill.y);
        context.lineTo(pill.x, pill.y + pill.length);
        context.stroke();
      });

      animationId = window.requestAnimationFrame(render);
    };

    render();

    const handleResize = () => {
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
      initPills();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.cancelAnimationFrame(animationId);
      window.removeEventListener("resize", handleResize);
    };
  }, [isDarkMode]);

  return (
    <canvas 
      ref={canvasRef} 
      className="absolute inset-0 h-full w-full opacity-80" 
    />
  );
}
