import boto3
import csv
from itertools import chain, combinations
from botocore.exceptions import ClientError
import time

# Only AMD A-series types
AMD_A_SERIES_INSTANCES = ["m5a", "r5a", "c6a", "m6a", "t3a", "r6a", "hpc6a", "g4ad", "m7a", "c7a", "r7a"]

def get_filtered_instance_types(region, exact_vcpus, exact_memory_gib):
    ec2 = boto3.client('ec2', region_name=region)
    filters = [
        {'Name': 'vcpu-info.default-vcpus', 'Values': [str(exact_vcpus)]},
        {'Name': 'memory-info.size-in-mib', 'Values': [str(int(exact_memory_gib * 1024))]},
        {'Name': 'supported-usage-class', 'Values': ['spot']}
    ]
    instance_types = []
    paginator = ec2.get_paginator('describe_instance_types')
    for page in paginator.paginate(Filters=filters):
        for it in page['InstanceTypes']:
            if any(it['InstanceType'].startswith(prefix) for prefix in AMD_A_SERIES_INSTANCES):
                instance_types.append(it['InstanceType'])
    return instance_types 

def powerset(iterable, min_size=3):
    s = list(iterable)
    return [list(comb) for comb in chain.from_iterable(combinations(s, r) for r in range(min_size, len(s)+1))]
def get_average_spot_placement_score(region, instance_types):
    ec2 = boto3.client('ec2', region_name=region)
    try:
        response = ec2.get_spot_placement_scores(
            InstanceTypes=instance_types,
            TargetCapacity=1,
            SingleAvailabilityZone=False,
            RegionNames=[region]
        )
        scores = []
        for rec in response.get('SpotPlacementScores', []):
            scores.append(rec['Score'])
        return sum(scores) / len(scores) if scores else 0.0
    except ClientError as e:
        print(f"[Score API Error] {e}")
        return 0.0


def get_average_spot_price(region, instance_types):
    ec2 = boto3.client('ec2', region_name=region)
    prices = []
    for itype in instance_types:
        try:
            response = ec2.describe_spot_price_history(
                InstanceTypes=[itype],
                ProductDescriptions=['Linux/UNIX'],
                StartTime=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                MaxResults=1
            )
            for history in response['SpotPriceHistory']:
                prices.append(float(history['SpotPrice']))
        except ClientError as e:
            print(f"[Price API Error for {itype}] {e}")
            continue
    return sum(prices) / len(prices) if prices else 0.0
def main():
    region = "us-east-1"
    exact_vcpus = int(input("Enter exact number of vCPUs: "))
    exact_memory = float(input("Enter exact memory (GiB): "))
    output_file = "spot_instance_scores.csv"

    print(f"\n📍 Region: {region}")
    print("🔍 Fetching instance types...")
    instance_types = get_filtered_instance_types(region, exact_vcpus, exact_memory)

    if not instance_types:
        print("❌ No matching AMD A-series spot instances found.")
        return

    print(f"✅ Found {len(instance_types)} eligible instance types: {instance_types}")

    subsets = powerset(instance_types, min_size=3)
    print(f"🧮 Evaluating {len(subsets)} combinations...")

    results = []

    for idx, subset in enumerate(subsets, start=1):
        print(f" Subset {idx}/{len(subsets)}: {subset}")

        avg_score = get_average_spot_placement_score(region, subset)
        avg_price = get_average_spot_price(region, subset)

        if avg_score == 0.0:
            print("⚠️ Skipping due to 0 placement score.")
            continue

        results.append({
            "instance_set": ', '.join(subset),
            "average_score": round(avg_score, 2),
            "average_price": round(avg_price, 4),
            "count": len(subset)
        })
    # Sort by highest score first, then by lowest price
    results.sort(key=lambda x: (-x["average_score"], x["average_price"]))

    print("\n✅ Top combinations:")
    for row in results[:5]:
        print(f"💡 {row['instance_set']} | Score: {row['average_score']} | Price: ${row['average_price']}")

    # Write results to CSV
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ["instance_set", "average_score", "average_price", "count"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n📁 Results saved to {output_file}")
if __name__ == '__main__':
    main()
