import { Spinner } from "@/components/ui/spinner";

export function PentagonSpinner() {
    const spinners = [
        { color: "text-red-500" },
        { color: "text-green-500" },
        { color: "text-blue-500" },
        { color: "text-yellow-500" },
        { color: "text-purple-500" },
    ];

    return (
        <div className="flex h-full w-full min-h-[50vh] items-center justify-center p-8">
            <div className="relative size-32 sm:size-40 animate-[spin_3s_linear_infinite]">
                {spinners.map((s, i) => {
                    const angle = -90 + i * 72;
                    // Using a fixed radius for the formation
                    const radius = "3.5rem";

                    const style = {
                        position: "absolute",
                        top: "50%",
                        left: "50%",
                        transform: `translate(-50%, -50%) rotate(${angle}deg) translate(${radius}) rotate(${-angle}deg)`,
                    } as React.CSSProperties;

                    return (
                        <div key={i} style={style}>
                            <Spinner className={`size-8 sm:size-10 ${s.color}`} />
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
